"""
File Manager for OJ Problem Editorial Downloader
Handles file operations, directory management, and file utilities with comprehensive error handling
"""

import os
import json
import shutil
import stat
import tempfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import logging

# Import comprehensive error handling
from utils.error_handler import (
    FileSystemError, handle_exception, ErrorDetector, 
    error_reporter, ErrorCategory, ErrorSeverity
)

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
    
    @handle_exception
    def ensure_directory(self, path: Union[str, Path]) -> Path:
        """
        Ensure directory exists with comprehensive error handling and validation
        
        Args:
            path (Union[str, Path]): Directory path
            
        Returns:
            Path: Path object of the directory
            
        Raises:
            FileSystemError: If directory creation fails
        """
        try:
            path_obj = Path(path)
            
            # Validate path
            if not str(path_obj).strip():
                raise FileSystemError("Empty path provided")
            
            # Check for invalid characters
            invalid_chars = '<>:"|?*' if os.name == 'nt' else '\0'
            if any(char in str(path_obj) for char in invalid_chars):
                raise FileSystemError(f"Path contains invalid characters: {path_obj}")
            
            # Check path length (Windows has 260 char limit)
            if len(str(path_obj)) > 250:
                raise FileSystemError(f"Path too long ({len(str(path_obj))} chars): {path_obj}")
            
            # Check if path already exists and is not a directory
            if path_obj.exists() and not path_obj.is_dir():
                raise FileSystemError(f"Path exists but is not a directory: {path_obj}")
            
            # Check disk space if creating new directory
            if not path_obj.exists():
                parent = path_obj.parent
                if not ErrorDetector.check_disk_space(str(parent), required_mb=10):
                    logger.warning(f"Low disk space when creating directory: {path_obj}")
            
            # Create directory with proper error handling
            try:
                path_obj.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                raise FileSystemError(f"Permission denied creating directory: {path_obj}", str(path_obj), e)
            except OSError as e:
                if e.errno == 36:  # File name too long
                    raise FileSystemError(f"File name too long: {path_obj}", str(path_obj), e)
                elif e.errno == 28:  # No space left on device
                    raise FileSystemError(f"No disk space available: {path_obj}", str(path_obj), e)
                else:
                    raise FileSystemError(f"OS error creating directory: {path_obj}", str(path_obj), e)
            
            # Verify directory was created and is accessible
            if not path_obj.exists():
                raise FileSystemError(f"Directory creation appeared to succeed but directory not found: {path_obj}")
            
            if not path_obj.is_dir():
                raise FileSystemError(f"Created path is not a directory: {path_obj}")
            
            # Test write permissions
            try:
                test_file = path_obj / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                logger.warning(f"Directory created but not writable: {path_obj}: {e}")
            
            logger.debug(f"Directory ensured: {path_obj}")
            return path_obj
            
        except FileSystemError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error ensuring directory {path}: {e}")
            raise FileSystemError(f"Failed to ensure directory: {str(e)}", str(path), e)
    
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
    
    @handle_exception
    def save_json(self, data: Dict[str, Any], filepath: Union[str, Path], 
                  indent: int = 2) -> bool:
        """
        Save data to JSON file with comprehensive error handling
        
        Args:
            data (Dict[str, Any]): Data to save
            filepath (Union[str, Path]): File path
            indent (int): JSON indentation
            
        Returns:
            bool: True if successful
            
        Raises:
            FileSystemError: If file operations fail
        """
        if data is None:
            raise FileSystemError("Cannot save None data to JSON file")
        
        try:
            filepath = Path(filepath)
            
            # Validate file path
            if not str(filepath).strip():
                raise FileSystemError("Empty filepath provided")
            
            # Ensure parent directory exists
            self.ensure_directory(filepath.parent)
            
            # Check disk space
            if not ErrorDetector.check_disk_space(str(filepath.parent), required_mb=5):
                raise FileSystemError(f"Insufficient disk space to save JSON: {filepath}")
            
            # Test data serialization first
            try:
                json_str = json.dumps(data, indent=indent, ensure_ascii=False)
            except (TypeError, ValueError) as e:
                raise FileSystemError(f"Data cannot be serialized to JSON: {str(e)}", str(filepath), e)
            
            # Write to temporary file first for atomic operation
            temp_file = filepath.with_suffix('.tmp')
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                
                # Verify file was written correctly
                if temp_file.stat().st_size == 0:
                    raise FileSystemError("JSON file was written but is empty")
                
                # Verify JSON can be read back
                with open(temp_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                
                # Atomic move to final location
                shutil.move(str(temp_file), str(filepath))
                
            except PermissionError as e:
                raise FileSystemError(f"Permission denied writing JSON file: {filepath}", str(filepath), e)
            except OSError as e:
                raise FileSystemError(f"OS error writing JSON file: {filepath}", str(filepath), e)
            finally:
                # Clean up temp file if it exists
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception:
                    pass
            
            logger.info(f"JSON data saved to: {filepath}")
            return True
            
        except FileSystemError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving JSON to {filepath}: {e}")
            raise FileSystemError(f"Failed to save JSON: {str(e)}", str(filepath), e)
    
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
    
    # PDF-specific file management functions
    
    def generate_pdf_filename(self, platform: str, contest: str, problem: str, 
                             suffix: str = "") -> str:
        """
        Generate PDF filename following naming convention: platform_contest_problem.pdf
        
        Args:
            platform (str): Platform name (e.g., 'atcoder', 'codeforces', 'spoj')
            contest (str): Contest identifier
            problem (str): Problem identifier
            suffix (str): Optional suffix for filename
            
        Returns:
            str: Generated filename
        """
        try:
            # Normalize platform name
            platform = platform.lower().strip()
            
            # Clean contest and problem identifiers
            contest = self.safe_filename(contest.strip())
            problem = self.safe_filename(problem.strip())
            
            # Build base filename
            if suffix:
                suffix = self.safe_filename(suffix.strip())
                filename = f"{platform}_{contest}_{problem}_{suffix}.pdf"
            else:
                filename = f"{platform}_{contest}_{problem}.pdf"
            
            # Ensure filename is safe
            filename = self.safe_filename(filename)
            
            # Ensure it ends with .pdf
            if not filename.lower().endswith('.pdf'):
                filename = filename + '.pdf'
            
            logger.debug(f"Generated PDF filename: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Failed to generate PDF filename: {e}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"problem_{timestamp}.pdf"
    
    def create_organized_directory_structure(self, base_output_dir: Union[str, Path], 
                                           platform: str, contest: Optional[str] = None) -> Path:
        """
        Create organized directory structure: base_dir/platform/contest/
        
        Args:
            base_output_dir (Union[str, Path]): Base output directory
            platform (str): Platform name
            contest (str, optional): Contest identifier
            
        Returns:
            Path: Created directory path
        """
        try:
            base_dir = Path(base_output_dir)
            
            # Create platform directory
            platform_dir = base_dir / platform.lower().strip()
            self.ensure_directory(platform_dir)
            
            if contest:
                # Create contest directory
                contest_safe = self.safe_filename(contest.strip())
                contest_dir = platform_dir / contest_safe
                self.ensure_directory(contest_dir)
                return contest_dir
            
            return platform_dir
            
        except Exception as e:
            logger.error(f"Failed to create organized directory structure: {e}")
            # Fallback to base directory
            return Path(base_output_dir)
    
    def check_existing_file(self, filepath: Union[str, Path], 
                           check_content: bool = False) -> Dict[str, Any]:
        """
        Check if file exists and provide information for overwrite decisions
        
        Args:
            filepath (Union[str, Path]): File path to check
            check_content (bool): Whether to check file content integrity
            
        Returns:
            Dict[str, Any]: File existence information
        """
        try:
            filepath = Path(filepath)
            
            result = {
                'exists': False,
                'path': str(filepath),
                'size': 0,
                'modified': None,
                'readable': False,
                'writable': False,
                'valid_pdf': False,
                'recommendation': 'create'
            }
            
            if not filepath.exists():
                result['recommendation'] = 'create'
                return result
            
            result['exists'] = True
            
            # Get file stats
            stat_info = filepath.stat()
            result['size'] = stat_info.st_size
            result['modified'] = datetime.fromtimestamp(stat_info.st_mtime)
            
            # Check permissions
            result['readable'] = os.access(filepath, os.R_OK)
            result['writable'] = os.access(filepath, os.W_OK)
            
            # Check if it's a valid PDF (basic check)
            if check_content and filepath.suffix.lower() == '.pdf':
                try:
                    with open(filepath, 'rb') as f:
                        header = f.read(8)
                        result['valid_pdf'] = header.startswith(b'%PDF-')
                except Exception:
                    result['valid_pdf'] = False
            
            # Provide recommendation
            if result['size'] == 0:
                result['recommendation'] = 'overwrite'  # Empty file
            elif not result['valid_pdf'] and filepath.suffix.lower() == '.pdf':
                result['recommendation'] = 'overwrite'  # Corrupted PDF
            else:
                result['recommendation'] = 'prompt'  # Valid existing file
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to check existing file {filepath}: {e}")
            return {
                'exists': False,
                'path': str(filepath),
                'recommendation': 'create',
                'error': str(e)
            }
    
    def handle_file_overwrite(self, filepath: Union[str, Path], 
                             action: str = 'prompt') -> Tuple[bool, Path]:
        """
        Handle file overwrite based on action
        
        Args:
            filepath (Union[str, Path]): Target file path
            action (str): Action to take ('overwrite', 'skip', 'rename', 'prompt')
            
        Returns:
            Tuple[bool, Path]: (should_proceed, final_filepath)
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return True, filepath
            
            if action == 'overwrite':
                # Create backup if file is significant
                if filepath.stat().st_size > 1024:  # > 1KB
                    backup_path = filepath.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                    shutil.copy2(filepath, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                return True, filepath
            
            elif action == 'skip':
                logger.info(f"Skipping existing file: {filepath}")
                return False, filepath
            
            elif action == 'rename':
                new_filepath = self.get_unique_filename(filepath)
                logger.info(f"Using unique filename: {new_filepath}")
                return True, new_filepath
            
            elif action == 'prompt':
                # For CLI applications, we'll default to rename to avoid blocking
                # This can be overridden by calling code for interactive prompts
                logger.warning(f"File exists, using unique name: {filepath}")
                new_filepath = self.get_unique_filename(filepath)
                return True, new_filepath
            
            else:
                logger.error(f"Unknown overwrite action: {action}")
                return False, Path(filepath)
            
        except Exception as e:
            logger.error(f"Failed to handle file overwrite for {filepath}: {e}")
            return False, Path(filepath)
    
    def validate_file_permissions(self, filepath: Union[str, Path], 
                                 create_if_missing: bool = True) -> Dict[str, Any]:
        """
        Validate file and directory permissions
        
        Args:
            filepath (Union[str, Path]): File path to validate
            create_if_missing (bool): Create parent directories if missing
            
        Returns:
            Dict[str, bool]: Permission validation results
        """
        try:
            filepath = Path(filepath)
            
            result = {
                'parent_exists': False,
                'parent_writable': False,
                'file_exists': False,
                'file_readable': False,
                'file_writable': False,
                'can_create': False,
                'valid': False
            }
            
            # Check parent directory
            parent_dir = filepath.parent
            result['parent_exists'] = parent_dir.exists()
            
            if not result['parent_exists'] and create_if_missing:
                try:
                    self.ensure_directory(parent_dir)
                    result['parent_exists'] = True
                except Exception as e:
                    logger.error(f"Failed to create parent directory: {e}")
                    return result
            
            if result['parent_exists']:
                result['parent_writable'] = os.access(parent_dir, os.W_OK)
            
            # Check file
            result['file_exists'] = filepath.exists()
            
            if result['file_exists']:
                result['file_readable'] = os.access(filepath, os.R_OK)
                result['file_writable'] = os.access(filepath, os.W_OK)
            
            # Determine if we can create/write the file
            result['can_create'] = result['parent_exists'] and result['parent_writable']
            
            # Overall validation
            if result['file_exists']:
                result['valid'] = result['file_writable']
            else:
                result['valid'] = result['can_create']
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate permissions for {filepath}: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def validate_output_directory(self, directory: Union[str, Path], 
                                 create_if_missing: bool = True) -> Dict[str, Any]:
        """
        Validate output directory selection
        
        Args:
            directory (Union[str, Path]): Directory path to validate
            create_if_missing (bool): Create directory if it doesn't exist
            
        Returns:
            Dict[str, Any]: Validation results
        """
        try:
            directory = Path(directory)
            
            result = {
                'path': str(directory),
                'exists': False,
                'is_directory': False,
                'writable': False,
                'readable': False,
                'space_available': 0,
                'valid': False,
                'issues': []
            }
            
            # Check if path exists
            result['exists'] = directory.exists()
            
            if not result['exists']:
                if create_if_missing:
                    try:
                        self.ensure_directory(directory)
                        result['exists'] = True
                        result['is_directory'] = True
                    except Exception as e:
                        result['issues'].append(f"Cannot create directory: {e}")
                        return result
                else:
                    result['issues'].append("Directory does not exist")
                    return result
            
            # Check if it's a directory
            result['is_directory'] = directory.is_dir()
            if not result['is_directory']:
                result['issues'].append("Path is not a directory")
                return result
            
            # Check permissions
            result['writable'] = os.access(directory, os.W_OK)
            result['readable'] = os.access(directory, os.R_OK)
            
            if not result['writable']:
                result['issues'].append("Directory is not writable")
            
            if not result['readable']:
                result['issues'].append("Directory is not readable")
            
            # Check available space (in MB)
            try:
                stat_result = os.statvfs(directory)
                available_bytes = stat_result.f_bavail * stat_result.f_frsize
                result['space_available'] = round(available_bytes / (1024 * 1024), 2)
                
                if result['space_available'] < 10:  # Less than 10MB
                    result['issues'].append("Low disk space available")
            except Exception as e:
                result['issues'].append(f"Cannot check disk space: {e}")
            
            # Overall validation
            result['valid'] = (result['exists'] and result['is_directory'] and 
                             result['writable'] and result['readable'])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate output directory {directory}: {e}")
            return {
                'path': str(directory),
                'valid': False,
                'issues': [f"Validation error: {e}"]
            }
    
    def generate_unique_pdf_filename(self, base_path: Union[str, Path], 
                                   platform: str, contest: str, problem: str,
                                   max_attempts: int = 1000) -> Path:
        """
        Generate unique PDF filename to avoid conflicts
        
        Args:
            base_path (Union[str, Path]): Base directory path
            platform (str): Platform name
            contest (str): Contest identifier
            problem (str): Problem identifier
            max_attempts (int): Maximum attempts to find unique name
            
        Returns:
            Path: Unique file path
        """
        try:
            base_path = Path(base_path)
            
            # Generate base filename
            base_filename = self.generate_pdf_filename(platform, contest, problem)
            filepath = base_path / base_filename
            
            if not filepath.exists():
                return filepath
            
            # Generate variations with counter
            base_name = filepath.stem
            extension = filepath.suffix
            
            for i in range(1, max_attempts + 1):
                new_filename = f"{base_name}_{i:03d}{extension}"
                new_filepath = base_path / new_filename
                if not new_filepath.exists():
                    logger.info(f"Generated unique filename: {new_filename}")
                    return new_filepath
            
            # Fallback with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
            fallback_filename = f"{base_name}_{timestamp}{extension}"
            fallback_filepath = base_path / fallback_filename
            
            logger.warning(f"Used timestamp fallback: {fallback_filename}")
            return fallback_filepath
            
        except Exception as e:
            logger.error(f"Failed to generate unique PDF filename: {e}")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return Path(base_path) / f"problem_{timestamp}.pdf"
    
    def cleanup_temporary_files(self, patterns: Optional[List[str]] = None, 
                              max_age_hours: int = 24) -> Dict[str, int]:
        """
        Clean up temporary files with specific patterns
        
        Args:
            patterns (List[str]): File patterns to clean (default: common temp patterns)
            max_age_hours (int): Maximum age in hours
            
        Returns:
            Dict[str, int]: Cleanup statistics
        """
        try:
            if patterns is None:
                patterns = [
                    '*.tmp',
                    '*.temp',
                    'temp_*',
                    '*.partial',
                    '*.download',
                    '.DS_Store',
                    'Thumbs.db',
                    '*.backup_*'
                ]
            
            current_time = datetime.now().timestamp()
            max_age_seconds = max_age_hours * 3600
            
            stats = {
                'files_checked': 0,
                'files_deleted': 0,
                'bytes_freed': 0,
                'errors': 0
            }
            
            # Clean temp directory
            for pattern in patterns:
                if self.temp_dir.exists():
                    for file_path in self.temp_dir.rglob(pattern):
                        if file_path.is_file():
                            stats['files_checked'] += 1
                            try:
                                file_age = current_time - file_path.stat().st_mtime
                                if file_age > max_age_seconds:
                                    file_size = file_path.stat().st_size
                                    file_path.unlink()
                                    stats['files_deleted'] += 1
                                    stats['bytes_freed'] += file_size
                            except Exception as e:
                                stats['errors'] += 1
                                logger.warning(f"Failed to delete temp file {file_path}: {e}")
            
            # Clean system temp directory for our files
            try:
                system_temp = Path(tempfile.gettempdir())
                for pattern in ['oj_downloader_*', 'pdf_temp_*']:
                    for file_path in system_temp.glob(pattern):
                        if file_path.is_file():
                            stats['files_checked'] += 1
                            try:
                                file_age = current_time - file_path.stat().st_mtime
                                if file_age > max_age_seconds:
                                    file_size = file_path.stat().st_size
                                    file_path.unlink()
                                    stats['files_deleted'] += 1
                                    stats['bytes_freed'] += file_size
                            except Exception as e:
                                stats['errors'] += 1
                                logger.warning(f"Failed to delete system temp file {file_path}: {e}")
            except Exception as e:
                logger.warning(f"Failed to access system temp directory: {e}")
                stats['errors'] += 1
            
            logger.info(f"Cleanup completed: {stats['files_deleted']} files deleted, "
                       f"{stats['bytes_freed']} bytes freed")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup temporary files: {e}")
            return {
                'files_checked': 0,
                'files_deleted': 0,
                'bytes_freed': 0,
                'errors': 1
            }
    
    def validate_path_security(self, filepath: Union[str, Path], 
                             allowed_base_paths: Optional[List[Union[str, Path]]] = None) -> Dict[str, Any]:
        """
        Validate file path for security (prevent directory traversal, etc.)
        
        Args:
            filepath (Union[str, Path]): File path to validate
            allowed_base_paths (List[Union[str, Path]]): Allowed base directories
            
        Returns:
            Dict[str, Any]: Security validation results
        """
        try:
            filepath = Path(filepath).resolve()  # Resolve to absolute path
            
            result = {
                'path': str(filepath),
                'safe': True,
                'issues': []
            }
            
            # Check for directory traversal attempts
            path_str = str(filepath)
            dangerous_patterns = ['../', '..\\', '/../', '\\..\\', '%2e%2e', '%2f', '%5c']
            
            for pattern in dangerous_patterns:
                if pattern in path_str.lower():
                    result['safe'] = False
                    result['issues'].append(f"Potential directory traversal: {pattern}")
            
            # Check for suspicious filenames
            suspicious_names = ['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'lpt1', 'lpt2']
            if filepath.stem.lower() in suspicious_names:
                result['safe'] = False
                result['issues'].append(f"Suspicious filename: {filepath.stem}")
            
            # Check against allowed base paths
            if allowed_base_paths:
                path_allowed = False
                for base_path in allowed_base_paths:
                    base_path = Path(base_path).resolve()
                    try:
                        filepath.relative_to(base_path)
                        path_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not path_allowed:
                    result['safe'] = False
                    result['issues'].append("Path outside allowed directories")
            
            # Check filename length
            if len(filepath.name) > 255:
                result['safe'] = False
                result['issues'].append("Filename too long")
            
            # Check path length
            if len(str(filepath)) > 4096:
                result['safe'] = False
                result['issues'].append("Path too long")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate path security for {filepath}: {e}")
            return {
                'path': str(filepath),
                'safe': False,
                'issues': [f"Validation error: {e}"]
            }
    
    def get_pdf_file_info(self, filepath: Union[str, Path]) -> Dict[str, Any]:
        """
        Get detailed information about a PDF file
        
        Args:
            filepath (Union[str, Path]): PDF file path
            
        Returns:
            Dict[str, Any]: PDF file information
        """
        try:
            filepath = Path(filepath)
            
            # Get basic file info
            info = self.get_file_info(filepath)
            if not info:
                return {'valid': False, 'error': 'File not found'}
            
            # Add PDF-specific information
            pdf_info = {
                **info,
                'is_pdf': filepath.suffix.lower() == '.pdf',
                'valid_pdf': False,
                'pdf_version': None,
                'encrypted': False,
                'pages': 0
            }
            
            if pdf_info['is_pdf'] and filepath.exists():
                try:
                    with open(filepath, 'rb') as f:
                        # Read first few bytes to check PDF header
                        header = f.read(8)
                        if header.startswith(b'%PDF-'):
                            pdf_info['valid_pdf'] = True
                            # Extract version
                            version_match = re.search(rb'%PDF-(\d\.\d)', header + f.read(32))
                            if version_match:
                                pdf_info['pdf_version'] = version_match.group(1).decode()
                        
                        # Basic check for encryption (look for /Encrypt)
                        f.seek(0)
                        content = f.read(min(8192, filepath.stat().st_size))  # Read first 8KB
                        pdf_info['encrypted'] = b'/Encrypt' in content
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze PDF content: {e}")
            
            return pdf_info
            
        except Exception as e:
            logger.error(f"Failed to get PDF file info for {filepath}: {e}")
            return {
                'valid': False,
                'error': str(e)
            }