from rest_framework import serializers


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload requests"""
    
    document = serializers.FileField(
        required=True,
        help_text="Document file (PDF, PNG, JPG, JPEG)"
    )
    document_type = serializers.ChoiceField(
        choices=[
            ('certificates', 'Certificates/Trainings'),
            ('job_history', 'Job History/Work Experience'),
            ('skills', 'Skills/Competencies'),
            ('milestones', 'Career Milestones'),
            ('community_contributions', 'Community Contributions')
        ],
        default='certificates',
        help_text="Type of document being uploaded"
    )
    store_file = serializers.BooleanField(
        default=True,
        help_text="Whether to store the file in Supabase"
    )
    
    def validate_document(self, value):
        """Validate document file"""
        # Check file size (10MB max)
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File size exceeds maximum limit of 10MB. Current size: {value.size / (1024*1024):.2f}MB"
            )
        
        # Check file extension
        allowed_extensions = ['pdf', 'png', 'jpg', 'jpeg']
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in allowed_extensions:
            raise serializers.ValidationError(
                f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        return value


class ExtractionResponseSerializer(serializers.Serializer):
    """Serializer for extraction response"""
    
    success = serializers.BooleanField()
    document_type = serializers.CharField()
    extracted_data = serializers.JSONField()
    file_info = serializers.JSONField(required=False)
    storage_info = serializers.JSONField(required=False)
    error = serializers.CharField(required=False)
    timestamp = serializers.DateTimeField()


class DocumentTypeSerializer(serializers.Serializer):
    """Serializer for document types listing"""
    
    document_types = serializers.ListField(
        child=serializers.CharField()
    )
    
    description = serializers.DictField(
        child=serializers.CharField()
    )


class HealthCheckSerializer(serializers.Serializer):
    """Serializer for health check response"""
    
    status = serializers.CharField()
    services = serializers.DictField()
    timestamp = serializers.DateTimeField()
