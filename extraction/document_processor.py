import PyPDF2
from io import BytesIO
from PIL import Image


class DocumentProcessor:
    """Utility class for processing different document types"""
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """
        Extract text content from PDF file
        
        Args:
            file_content: Binary content of PDF file
            
        Returns:
            Extracted text as string
        """
        try:
            pdf_file = BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = []
            for page in pdf_reader.pages:
                text_content.append(page.extract_text())
            
            return "\n\n".join(text_content)
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    @staticmethod
    def validate_image(file_content: bytes) -> bool:
        """
        Validate if the file is a valid image
        
        Args:
            file_content: Binary content of image file
            
        Returns:
            Boolean indicating if image is valid
        """
        try:
            image = Image.open(BytesIO(file_content))
            image.verify()
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_image_info(file_content: bytes) -> dict:
        """
        Get information about an image
        
        Args:
            file_content: Binary content of image file
            
        Returns:
            Dictionary with image information
        """
        try:
            image = Image.open(BytesIO(file_content))
            return {
                "format": image.format,
                "mode": image.mode,
                "size": image.size,
                "width": image.width,
                "height": image.height
            }
        except Exception as e:
            return {"error": str(e)}
    
    @staticmethod
    def convert_to_jpeg(file_content: bytes) -> bytes:
        """
        Convert image to JPEG format
        
        Args:
            file_content: Binary content of image file
            
        Returns:
            JPEG image as bytes
        """
        try:
            image = Image.open(BytesIO(file_content))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as JPEG
            output = BytesIO()
            image.save(output, format='JPEG', quality=95)
            output.seek(0)
            return output.read()
        except Exception as e:
            raise Exception(f"Failed to convert image to JPEG: {str(e)}")
