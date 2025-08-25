"""
File Manager for OJ Problem Editorial Downloader
Handles file operations, directory management, and file utilities
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FileManager:
    """
    Utility class for managing files and directories
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize File Manager
        
        Args:
            base_dir (Optional[str]): Base directory for operations
        """
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.ensure_directory(self.base_dir)
        
        # Standard subdirectories
        self.cache_dir = self.base_dir / "cache"
        self.output_dir = self.base_dir / "output"
        self.temp_dir = self.base_dir / "temp"
        self.config_dir = self.base_dir / "config"
        
        # Create standard directories
        for directory in [self.cache_dir, self.output_dir, self.temp_dir, self.config_dir]:
            self.ensure_directory(directory)
    
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """
        Ensure directory exists, create if it doesn't
        
        Args:
            path (Union[str, Path]): Directory path
            
        Returns:
            Path: Path object of the directory
        """
        try:
            path_obj = Path(path)
            path_obj.mkdir(parents=True, exist_ok=True)
            return path_obj
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise
    
    def safe_filename(self, filename: str, max_length: int = 255) -> str:
        """
        Create a safe filename by removing/replacing invalid characters
        
        Args:
            filename (str): Original filename
            max_length (int): Maximum filename length
            
        Returns:
            str: Safe filename
        """
        try:
            # Remove or replace invalid characters
            invalid_chars = '<>:"/\\|?*'
            safe_name = filename
            
            for char in invalid_chars:
                safe_name = safe_name.replace(char, '_')
            
            # Remove multiple consecutive underscores
            while '__' in safe_name:
                safe_name = safe_name.replace('__', '_')
            
            # Trim whitespace and dots
            safe_name = safe_name.strip(' .')
            
            # Ensure length limit
            if len(safe_name) > max_length:
                name_part, ext_part = os.path.splitext(safe_name)
                max_name_length = max_length - len(ext_part)
                safe_name = name_part[:max_name_length] + ext_part
            
            # Ensure it's not empty
            if not safe_name or safe_name in ['.', '..']:
                safe_name = f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return safe_name
            
        except Exception as e:
            logger.error(f"Error creating safe filename from '{filename}': {e}")
            return f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def save_json(self, data: Dict[str, Any], filepath: Union[str, Path], 
                  indent: int = 2) -> bool:
        """
        Save data to JSON file
        
        Args:
            data (Dict[str, Any]): Data to save
            filepath (Union[str, Path]): File path
            indent (int): JSON indentation
            
        Returns:
            bool: True if successful
        """
        try:
            filepath = Path(filepath)
            self.ensure_directory(filepath.parent)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            logger.info(f"JSON data saved to: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save JSON to {filepath}: {e}")
            return False
    
    def load_json(self, filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Load data from JSON file
        
        Args:
            filepath (Union[str, Path]): File path
            
        Returns:
            Optional[Dict[str, Any]]: Loaded data or None if failed
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                logger.warning(f"JSON file not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"JSON data loaded from: {filepath}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load JSON from {filepath}: {e}")
            return None
    
    def save_text(self, text: str, filepath: Union[str, Path], 
                  encoding: str = 'utf-8') -> bool:
        """
        Save text to file
        
        Args:
            text (str): Text content
            filepath (Union[str, Path]): File path
            encoding (str): Text encoding
            
        Returns:
            bool: True if successful
        """
        try:
            filepath = Path(filepath)
            self.ensure_directory(filepath.parent)
            
            with open(filepath, 'w', encoding=encoding) as f:
                f.write(text)
            
            logger.info(f"Text saved to: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save text to {filepath}: {e}")
            return False
    
    def load_text(self, filepath: Union[str, Path], 
                  encoding: str = 'utf-8') -> Optional[str]:
        """
        Load text from file
        
        Args:
            filepath (Union[str, Path]): File path
            encoding (str): Text encoding
            
        Returns:
            Optional[str]: Text content or None if failed
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                logger.warning(f"Text file not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding=encoding) as f:
                text = f.read()
            
            logger.info(f"Text loaded from: {filepath}")
            return text
            
        except Exception as e:
            logger.error(f"Failed to load text from {filepath}: {e}")
            return None
    
    def copy_file(self, source: Union[str, Path], 
                  destination: Union[str, Path]) -> bool:
        """
        Copy file from source to destination
        
        Args:
            source (Union[str, Path]): Source file path
            destination (Union[str, Path]): Destination file path
            
        Returns:
            bool: True if successful
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            self.ensure_directory(dest_path.parent)
            shutil.copy2(source_path, dest_path)
            
            logger.info(f"File copied: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy file {source} to {destination}: {e}")
            return False
    
    def move_file(self, source: Union[str, Path], 
                  destination: Union[str, Path]) -> bool:
        """
        Move file from source to destination
        
        Args:
            source (Union[str, Path]): Source file path
            destination (Union[str, Path]): Destination file path
            
        Returns:
            bool: True if successful
        """
        try:
            source_path = Path(source)
            dest_path = Path(destination)
            
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return False
            
            self.ensure_directory(dest_path.parent)
            shutil.move(str(source_path), str(dest_path))
            
            logger.info(f"File moved: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to move file {source} to {destination}: {e}")
            return False
    
    def delete_file(self, filepath: Union[str, Path]) -> bool:
        """
        Delete file
        
        Args:
            filepath (Union[str, Path]): File path to delete
            
        Returns:
            bool: True if successful
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                logger.warning(f"File not found (already deleted?): {filepath}")
                return True
            
            if filepath.is_file():
                filepath.unlink()
                logger.info(f"File deleted: {filepath}")
                return True
            else:
                logger.error(f"Path is not a file: {filepath}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to delete file {filepath}: {e}")
            return False
    
    def delete_directory(self, dirpath: Union[str, Path], 
                        force: bool = False) -> bool:
        """
        Delete directory and its contents
        
        Args:
            dirpath (Union[str, Path]): Directory path to delete
            force (bool): Force deletion even if not empty
            
        Returns:
            bool: True if successful
        """
        try:
            dirpath = Path(dirpath)
            
            if not dirpath.exists():
                logger.warning(f"Directory not found (already deleted?): {dirpath}")
                return True
            
            if not dirpath.is_dir():
                logger.error(f"Path is not a directory: {dirpath}")
                return False
            
            if force:
                shutil.rmtree(dirpath)
            else:
                dirpath.rmdir()  # Only works if empty
            
            logger.info(f"Directory deleted: {dirpath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete directory {dirpath}: {e}")
            return False
    
    def list_files(self, directory: Union[str, Path], 
                   pattern: str = "*", recursive: bool = False) -> List[Path]:
        """
        List files in directory matching pattern
        
        Args:
            directory (Union[str, Path]): Directory to search
            pattern (str): File pattern (glob style)
            recursive (bool): Search recursively
            
        Returns:
            List[Path]: List of matching file paths
        """
        try:
            directory = Path(directory)
            
            if not directory.exists() or not directory.is_dir():
                logger.warning(f"Directory not found or not a directory: {directory}")
                return []
            
            if recursive:
                files = list(directory.rglob(pattern))
            else:
                files = list(directory.glob(pattern))
            
            # Filter to only files (not directories)
            files = [f for f in files if f.is_file()]
            
            logger.info(f"Found {len(files)} files matching '{pattern}' in {directory}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []
    
    def get_file_info(self, filepath: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """
        Get file information
        
        Args:
            filepath (Union[str, Path]): File path
            
        Returns:
            Optional[Dict[str, Any]]: File information or None if failed
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return None
            
            stat = filepath.stat()
            
            info = {
                'path': str(filepath),
                'name': filepath.name,
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'is_file': filepath.is_file(),
                'is_directory': filepath.is_dir(),
                'extension': filepath.suffix.lower(),
                'parent': str(filepath.parent)
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get file info for {filepath}: {e}")
            return None
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files
        
        Args:
            max_age_hours (int): Maximum age in hours for temp files
            
        Returns:
            int: Number of files deleted
        """
        try:
            if not self.temp_dir.exists():
                return 0
            
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0
            
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete temp file {file_path}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} temporary files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
            return 0
    
    def get_unique_filename(self, filepath: Union[str, Path]) -> Path:
        """
        Get unique filename by adding number suffix if file exists
        
        Args:
            filepath (Union[str, Path]): Desired file path
            
        Returns:
            Path: Unique file path
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return filepath
            
            base_name = filepath.stem
            extension = filepath.suffix
            parent = filepath.parent
            
            counter = 1
            while True:
                new_name = f"{base_name}_{counter}{extension}"
                new_path = parent / new_name
                if not new_path.exists():
                    return new_path
                counter += 1
                
                # Prevent infinite loop
                if counter > 1000:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_name = f"{base_name}_{timestamp}{extension}"
                    return parent / new_name
            
        except Exception as e:
            logger.error(f"Failed to get unique filename for {filepath}: {e}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return Path(f"file_{timestamp}.txt")
    
    def archive_directory(self, source_dir: Union[str, Path], 
                         archive_path: Union[str, Path], 
                         format: str = 'zip') -> bool:
        """
        Create archive of directory
        
        Args:
            source_dir (Union[str, Path]): Source directory
            archive_path (Union[str, Path]): Archive file path
            format (str): Archive format ('zip', 'tar', 'gztar', 'bztar', 'xztar')
            
        Returns:
            bool: True if successful
        """
        try:
            source_dir = Path(source_dir)
            archive_path = Path(archive_path)
            
            if not source_dir.exists() or not source_dir.is_dir():
                logger.error(f"Source directory not found: {source_dir}")
                return False
            
            self.ensure_directory(archive_path.parent)
            
            # Remove extension for shutil.make_archive
            archive_base = str(archive_path.with_suffix(''))
            
            shutil.make_archive(archive_base, format, source_dir)
            
            logger.info(f"Directory archived: {source_dir} -> {archive_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive directory {source_dir}: {e}")
            return False