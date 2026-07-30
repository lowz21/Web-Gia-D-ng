"""
Cloud Storage Service for Image Uploads
Supports Cloudinary and Supabase Storage with fallback to local storage.
"""
import os
import uuid
from werkzeug.utils import secure_filename


class CloudStorageService:
    """Base class for cloud storage services"""
    
    def upload_file(self, file, folder="uploads", public_id=None):
        """Upload a file to cloud storage"""
        raise NotImplementedError
    
    def delete_file(self, public_id):
        """Delete a file from cloud storage"""
        raise NotImplementedError
    
    def get_url(self, public_id):
        """Get the public URL for a file"""
        raise NotImplementedError


class CloudinaryStorage(CloudStorageService):
    """Cloudinary storage implementation"""
    
    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.api_key = os.getenv("CLOUDINARY_API_KEY")
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET")
        self._client = None
    
    @property
    def client(self):
        """Lazy load Cloudinary client"""
        if self._client is None:
            try:
                import cloudinary
                import cloudinary.uploader
                
                cloudinary.config(
                    cloud_name=self.cloud_name,
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )
                self._client = cloudinary.uploader
            except ImportError:
                raise ImportError("cloudinary package not installed. Install with: pip install cloudinary")
        return self._client
    
    def is_configured(self):
        """Check if Cloudinary is properly configured"""
        return all([self.cloud_name, self.api_key, self.api_secret])
    
    def upload_file(self, file, folder="uploads", public_id=None):
        """Upload file to Cloudinary"""
        if not self.is_configured():
            raise ValueError("Cloudinary not configured")
        
        # Generate unique public ID if not provided
        if public_id is None:
            public_id = f"{folder}/{uuid.uuid4().hex}"
        
        # Read file content
        file_content = file.read()
        file.seek(0)  # Reset file pointer
        
        # Upload to Cloudinary
        result = self.client.upload(
            file_content,
            public_id=public_id,
            folder=folder,
            resource_type="auto"
        )
        
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "version": result.get("version")
        }
    
    def delete_file(self, public_id):
        """Delete file from Cloudinary"""
        if not self.is_configured():
            raise ValueError("Cloudinary not configured")
        
        try:
            import cloudinary.api
            cloudinary.api.delete_resources([public_id])
            return True
        except Exception:
            return False
    
    def get_url(self, public_id):
        """Get Cloudinary URL for a public ID"""
        if not self.is_configured():
            raise ValueError("Cloudinary not configured")
        
        try:
            import cloudinary.utils
            return cloudinary.utils.cloudinary_url(public_id)[0]
        except Exception:
            return None


class SupabaseStorage(CloudStorageService):
    """Supabase Storage implementation"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.bucket = os.getenv("SUPABASE_BUCKET", "uploads")
        self._client = None
    
    @property
    def client(self):
        """Lazy load Supabase client"""
        if self._client is None:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
            except ImportError:
                raise ImportError("supabase package not installed. Install with: pip install supabase")
        return self._client
    
    def is_configured(self):
        """Check if Supabase is properly configured"""
        return all([self.url, self.key])
    
    def upload_file(self, file, folder="uploads", public_id=None):
        """Upload file to Supabase Storage"""
        if not self.is_configured():
            raise ValueError("Supabase not configured")
        
        # Generate unique filename if not provided
        if public_id is None:
            filename = secure_filename(file.filename)
            public_id = f"{folder}/{uuid.uuid4().hex}_{filename}"
        else:
            filename = public_id.split("/")[-1]
        
        # Read file content
        file_content = file.read()
        file.seek(0)  # Reset file pointer
        
        # Upload to Supabase
        try:
            result = self.client.storage.from_(self.bucket).upload(
                path=public_id,
                file=file_content,
                file_options={"content-type": file.content_type}
            )
            
            # Get public URL
            url = self.client.storage.from_(self.bucket).get_public_url(public_id)
            
            return {
                "url": url,
                "public_id": public_id,
                "path": result.get("path")
            }
        except Exception as e:
            raise Exception(f"Supabase upload failed: {str(e)}")
    
    def delete_file(self, public_id):
        """Delete file from Supabase Storage"""
        if not self.is_configured():
            raise ValueError("Supabase not configured")
        
        try:
            self.client.storage.from_(self.bucket).remove([public_id])
            return True
        except Exception:
            return False
    
    def get_url(self, public_id):
        """Get Supabase public URL for a file"""
        if not self.is_configured():
            raise ValueError("Supabase not configured")
        
        try:
            return self.client.storage.from_(self.bucket).get_public_url(public_id)
        except Exception:
            return None


class LocalStorage(CloudStorageService):
    """Local filesystem storage (fallback)"""
    
    def __init__(self, upload_folder="static/uploads"):
        self.upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)
    
    def upload_file(self, file, folder="uploads", public_id=None):
        """Upload file to local filesystem"""
        # Generate unique filename
        if public_id is None:
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
        else:
            unique_filename = public_id.split("/")[-1]
        
        # Create folder path
        folder_path = os.path.join(self.upload_folder, folder)
        os.makedirs(folder_path, exist_ok=True)
        
        # Save file
        file_path = os.path.join(folder_path, unique_filename)
        file.save(file_path)
        
        # Return relative path for URL
        relative_path = os.path.join(folder, unique_filename).replace("\\", "/")
        
        return {
            "url": f"/static/{relative_path}",
            "public_id": relative_path,
            "path": file_path
        }
    
    def delete_file(self, public_id):
        """Delete file from local filesystem"""
        try:
            file_path = os.path.join(self.upload_folder, public_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    def get_url(self, public_id):
        """Get local URL for a file"""
        return f"/static/{public_id}"


def get_storage_service():
    """
    Factory function to get the appropriate storage service based on environment.
    Priority: Cloudinary > Supabase > Local
    """
    # Try Cloudinary first
    cloudinary = CloudinaryStorage()
    if cloudinary.is_configured():
        return cloudinary
    
    # Try Supabase second
    supabase = SupabaseStorage()
    if supabase.is_configured():
        return supabase
    
    # Fall back to local storage
    return LocalStorage()


def upload_image(file, folder="uploads", public_id=None):
    """
    Convenience function to upload an image using the configured storage service.
    
    Args:
        file: File object from request.files
        folder: Folder path for storage
        public_id: Optional public ID for the file
    
    Returns:
        dict: Contains 'url' and 'public_id' of the uploaded file
    """
    storage = get_storage_service()
    return storage.upload_file(file, folder=folder, public_id=public_id)


def delete_image(public_id):
    """
    Convenience function to delete an image using the configured storage service.
    
    Args:
        public_id: Public ID of the file to delete
    
    Returns:
        bool: True if deletion was successful
    """
    storage = get_storage_service()
    return storage.delete_file(public_id)
