"""Serializer module for validating CSV file upload data."""

from rest_framework import serializers  # Import DRF serializers for validation
import codecs  # Import codecs to validate encoding values

class CSVFileSerializer(serializers.Serializer):
    """Serializer for validating CSV file uploads with delimiter and encoding options.

    Attributes:
        file: FileField for the uploaded CSV file.
        delimiter: CharField for the output delimiter (optional, defaults to tab).
        encoding: CharField for the file encoding (optional, defaults to utf-8).
    """

    # Define fields with help text for API documentation
    file = serializers.FileField(help_text="The CSV file to upload.")
    delimiter = serializers.CharField(
        required=False,  # Optional field
        max_length=2,  # Restrict to 2character
        allow_blank=True,  # Allow empty input
        default='\t',  # Default to tab if not provided
        help_text="Single-character delimiter for output (e.g., ',', '\\t', 'space')."
    )
    encoding = serializers.CharField(
        required=False,  # Optional field
        max_length=20,  # Reasonable length for encoding names
        allow_blank=True,  # Allow empty input
        default='utf-8',  # Default to UTF-8, widely used globally
        help_text="File encoding (e.g., 'utf-8', 'latin1')."
    )
    
    def validate_file(self, value):
        """Validate that the uploaded file is a CSV.

        Args:
            value: The uploaded file object.

        Returns:
            The file object if valid.

        Raises:
            ValidationError: If the file doesn't have a .csv extension.
        """
        # Check file extension (case-insensitive)
        if not value.name.lower().endswith('.csv'):
            raise serializers.ValidationError("Only CSV files are allowed.")
        return value  # Return the file if valid

    def validate_delimiter(self, value):
        """Convert and validate the output delimiter.

        Args:
            value: The delimiter string provided by the user.

        Returns:
            The validated delimiter character.

        Raises:
            ValidationError: If the delimiter is invalid.
        """
        # Handle blank input by returning default
        if not value:
            return '\t'
        # Define valid delimiters with their mappings
        valid_delimiters = {
            '\\t': '\t',  # Tab
            '\\n': '\n',  # Newline
            '\\r': '\r',  # Carriage return
            'space': ' ',  # Space (word)
            ' ': ' ',     # Space (character)
            ',': ',',     # Comma
            ';': ';',     # Semicolon
            '|': '|'      # Pipe (added for your use case)
        }
        # Check if input matches a valid delimiter
        if value.lower() in valid_delimiters:
            return valid_delimiters[value.lower()]
        # Raise error for invalid input
        raise serializers.ValidationError("Invalid delimiter. Use one of: comma, semicolon, tab, space, pipe.")

    def validate_encoding(self, value):
        """Ensure the encoding is supported by Python.

        Args:
            value: The encoding string provided by the user.

        Returns:
            The validated encoding string.

        Raises:
            ValidationError: If the encoding is unsupported.
        """
        # Handle blank input by returning default
        if not value:
            return 'utf-8'
        # Validate encoding against Python's codec registry
        try:
            codecs.lookup(value)
            return value
        except LookupError:
            raise serializers.ValidationError("Unsupported encoding.")