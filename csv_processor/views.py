"""View module for processing CSV files into formatted text output."""

from rest_framework.views import APIView  # Base class for DRF views
from rest_framework.response import Response  # DRF response object
from rest_framework import status  # HTTP status codes
from rest_framework.parsers import MultiPartParser, FormParser  # Parsers for file uploads
from django.http import HttpResponse  # Django response for file downloads
import csv  # Standard library for CSV parsing
import pandas as pd  # Pandas for data manipulation
import magic  # Library to detect file MIME types
from pandas.errors import EmptyDataError  # Pandas-specific error for empty files
import textwrap  # Utility for wrapping text
from io import TextIOWrapper  # Convert binary file to text stream
from .serializers import CSVFileSerializer  # Import the serializer

class CSVProcessorView(APIView):
    """API view for processing CSV files with specified delimiter output and column wrapping.

    Supports POST requests with multipart/form-data containing a CSV file, delimiter, and encoding.
    Returns a formatted text file with wrapped columns.
    """
    
    # Define parsers to handle file uploads
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        """Handle POST requests to process uploaded CSV files.

        Args:
            request: The HTTP request object containing file and parameters.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: A streamed text file with processed data.
            Response: An error response if validation or processing fails.
        """
        # Validate request data using the serializer
        serializer = CSVFileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract validated data
        csv_file = serializer.validated_data['file']  # Uploaded CSV file
        output_delimiter = serializer.validated_data['delimiter']  # Output delimiter (e.g., '|')
        encoding = serializer.validated_data['encoding']  # File encoding

        # Check file size (10MB limit)
        if csv_file.size > 10 * 1024 * 1024:
            return Response(
                {"error": "File too large. Maximum size allowed is 10MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        # Validate file type using python-magic
        try:
            file_content = csv_file.read(4096)  # Read first 4KB for MIME detection
            csv_file.seek(0)  # Reset file pointer
            file_type = magic.from_buffer(file_content, mime=True)  # Detect MIME type
            acceptable_types = ['text/csv', 'application/csv', 'application/vnd.ms-excel']
            if file_type not in acceptable_types:
                return Response(
                    {"error": f"Invalid file type: {file_type}. Please upload a valid CSV file."},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
                )
        except magic.MagicException as e:
            return Response(
                {"error": f"Error determining file type: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            # Wrap binary file in a text stream with specified encoding
            text_file = TextIOWrapper(csv_file.file, encoding=encoding)

            # Detect input delimiter using csv.Sniffer
            try:
                sample = text_file.read(1024)  # Read sample for delimiter detection
                text_file.seek(0)  # Reset pointer
                dialect = csv.Sniffer().sniff(sample)  # Sniff delimiter
                input_delimiter = dialect.delimiter  # Extract detected delimiter
            except csv.Error:
                input_delimiter = ','  # Fallback to comma if detection fails

            # Load CSV in chunks for scalability
            chunks = pd.read_csv(
                text_file,
                sep=input_delimiter,  # Use detected or fallback delimiter
                encoding=encoding,  # Apply specified encoding
                skipinitialspace=True,  # Trim leading spaces
                skip_blank_lines=True,  # Skip empty lines
                on_bad_lines='warn',  # Warn on malformed lines
                dtype=str,  # Treat all data as strings
                chunksize=1000  # Process 1000 rows per chunk
            )

            # Define generator for streaming output
            def generate_output():
                """Generate lines of formatted text incrementally."""
                first_chunk = True  # Flag for header processing
                for df in chunks:  # Iterate over DataFrame chunks
                    column_widths = self._calculate_column_widths(df)  # Compute widths
                    if first_chunk:
                        # Create header line with delimiter
                        header_line = output_delimiter.join(
                            str(col).ljust(column_widths[col]) for col in df.columns
                        )
                        yield header_line + "\n"  # Yield header
                        first_chunk = False  # Disable header for subsequent chunks
                    for _, row in df.iterrows():  # Process each row
                        lines = self._format_row(row, column_widths, output_delimiter)
                        for line in lines:
                            yield line + "\n"  # Yield each formatted line

            # Return streamed response
            response = HttpResponse(generate_output(), content_type='text/plain')
            response['Content-Disposition'] = 'attachment; filename="output.txt"'
            return response

        except UnicodeDecodeError as e:
            return Response(
                {"error": f"Encoding error: {str(e)}. Check the file encoding."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except csv.Error as e:
            return Response(
                {"error": f"CSV parsing error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except EmptyDataError:
            return Response(
                {"error": "The uploaded CSV file is empty."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Processing error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_column_widths(self, df):
        """Calculate column widths based on content for alignment.

        Args:
            df: Pandas DataFrame chunk to analyze.

        Returns:
            dict: Mapping of column names to their calculated widths.
        """
        column_widths = {}  # Store computed widths
        for col in df.columns:  # Iterate over columns
            header_len = len(str(col))  # Length of column header
            values = df[col].dropna().astype(str)  # Non-null values as strings
            # Calculate width: max of header or 90th percentile content, capped at 30
            width = header_len if values.empty else max(header_len, min(int(values.str.len().quantile(0.9)), 30))
            column_widths[col] = max(width, 15)  # Ensure minimum width of 15
        return column_widths

    def _format_row(self, row, column_widths, output_delimiter):
        """Format a single row with wrapped text, delimiter only on first line.

        Args:
            row: Pandas Series representing a row.
            column_widths: Dict of column widths.
            output_delimiter: String delimiter for the first line.

        Returns:
            list: List of formatted lines (strings).
        """
        wrapped_row_data = {}  # Store wrapped content per column
        max_wrapped_lines = 1  # Track maximum number of lines needed
        for col in row.index:  # Iterate over columns
            # Convert cell to string, empty if NaN
            cell_text = str(row[col]) if not pd.isna(row[col]) else ""
            # Wrap text to column width, ensure at least one line
            wrapped_lines = textwrap.wrap(cell_text, width=column_widths[col]) or [""]
            wrapped_row_data[col] = wrapped_lines
            max_wrapped_lines = max(max_wrapped_lines, len(wrapped_lines))

        result_lines = []  # Collect formatted lines
        # First line with delimiter
        first_line_cells = [
            wrapped_row_data[col][0].ljust(column_widths[col]) for col in row.index
        ]
        result_lines.append(output_delimiter.join(first_line_cells))  # Join with delimiter
        
        # Continuation lines with spaces only
        for i in range(1, max_wrapped_lines):
            continuation_line = ""  # Build line incrementally
            for col_idx, col in enumerate(row.index):
                # Get wrapped content or empty string
                cell_content = wrapped_row_data[col][i] if i < len(wrapped_row_data[col]) else ""
                padded_content = cell_content.ljust(column_widths[col])  # Pad to width
                # Add space between columns, not before first
                continuation_line += (" " if col_idx > 0 else "") + padded_content
            result_lines.append(continuation_line)  # Add line without delimiter
        
        return result_lines