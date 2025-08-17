"""
Data loader for the Data Analyst Agent.
"""
import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import pandas as pd
import sqlite3
import tempfile
import re
from .configs.settings import ALLOWED_EXTENSIONS, MAX_FILE_SIZE
from .utils.validation import validate_file_upload, sanitize_filename

def sanitize_filename(filename: str) -> str:
    filename = filename.split('/')[-1].split('\\')[-1]
    filename = re.sub(r'[<>:"|?*]', '_', filename)
    filename = filename.strip(' .')
    return filename if filename else "untitled"

class DataLoader:
    """Handles loading and basic processing of uploaded files."""
    
    def __init__(self):
        """Initialize data loader."""
        self.supported_extensions = ALLOWED_EXTENSIONS
        self.max_file_size = MAX_FILE_SIZE
        # Create a temporary directory for storing uploaded files
        self.temp_dir = tempfile.mkdtemp(prefix="data_agent_")
    def load_files(self, uploaded_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        
        """
        uploaded_files is a list of dicts:
        [
            {"filename": "question.txt", "content": b"...", "content_type": "text/plain"},
            ...
        ]
        Returns: dict {filename: saved_path}
        """
        file_map = {}
        for file_data in uploaded_files:
            try:
                filename = sanitize_filename(file_data.get("filename", ""))
                if not filename:
                    raise ValueError("Filename is required")

                save_path = os.path.join(self.temp_dir, filename)

                # Write file to disk
                with open(save_path, "wb") as f:
                    f.write(file_data.get("content", b""))

                file_map[filename] = save_path
            except Exception as e:
                # Log error but continue with next file
                print(f"[DataLoader] Error processing file {file_data.get('filename', 'unknown')}: {e}")

                # Optional: create an error marker file so sandbox can still reference it
                error_filename = f"ERROR_{file_data.get('filename', 'unknown') or 'untitled'}.txt"
                error_path = os.path.join(self.temp_dir, sanitize_filename(error_filename))
                with open(error_path, "w", encoding="utf-8") as ef:
                    ef.write(f"Error loading file: {str(e)}\n")
                
                # Store the error file in file_map so downstream code still sees it
                file_map[error_filename] = error_path
        return file_map
    
    def _process_single_file(self, file_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        filename = file_data.get('filename', '')
        content = file_data.get('content', b'')
        content_type = file_data.get('content_type', '')
        
        validation_result = validate_file_upload(
            filename, 
            len(content), 
            self.supported_extensions, 
            self.max_file_size
        )
        
        if not validation_result['valid']:
            raise ValueError(f"File validation failed: {'; '.join(validation_result['errors'])}")
        
        safe_filename = sanitize_filename(filename)
        file_extension = Path(safe_filename).suffix.lower()
        
        metadata = self._extract_metadata(content, file_extension)
        
        return {
            'name': safe_filename,
            'original_name': filename,
            'content': content,
            'size': len(content),
            'extension': file_extension,
            'content_type': content_type,
            'metadata': metadata,
            'validation_warnings': validation_result.get('warnings', [])
        }
    
    def _extract_metadata(self, content: bytes, extension: str) -> Dict[str, Any]:
        metadata = {
            'preview_available': False,
            'preview': '',
            'structure_info': ''
        }
        try:
            if extension == '.csv':
                metadata.update(self._analyze_csv(content))
            elif extension == '.json':
                metadata.update(self._analyze_json(content))
            elif extension == '.xlsx':
                metadata.update(self._analyze_excel(content))
            elif extension == '.txt':
                metadata.update(self._analyze_text(content))
            elif extension == '.sqlite':
                metadata.update(self._analyze_sqlite(content))
            elif extension == '.parquet':
                metadata.update(self._analyze_parquet(content))
            else:
                metadata['structure_info'] = f"Unsupported file type: {extension}"
        except Exception as e:
            metadata['analysis_error'] = str(e)
        return metadata
    
    def _analyze_csv(self, content: bytes) -> Dict[str, Any]:
        try:
            import io
            df = pd.read_csv(io.BytesIO(content))
            return {
                'file_type': 'CSV',
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'preview_available': True,
                'preview': df.head(5).to_string(index=False),
                'structure_info': f"CSV with {len(df)} rows and {len(df.columns)} columns",
                'memory_usage': int(df.memory_usage(deep=True).sum())
            }
        except Exception as e:
            return {'file_type': 'CSV', 'analysis_error': str(e)}
    
    def _analyze_json(self, content: bytes) -> Dict[str, Any]:
        try:
            text_content = content.decode('utf-8', errors='replace')
            data = json.loads(text_content)
            preview = json.dumps(data, indent=2)[:500].strip() + ("..." if len(str(data)) > 500 else "")
            if isinstance(data, dict):
                structure_info = f"JSON object with {len(data)} keys: {list(data.keys())[:10]}"
            elif isinstance(data, list):
                structure_info = f"JSON array with {len(data)} items"
                if data and isinstance(data[0], dict):
                    structure_info += f", sample keys: {list(data[0].keys())[:5]}"
            else:
                structure_info = f"JSON {type(data).__name__}"
            return {
                'file_type': 'JSON',
                'data_type': type(data).__name__,
                'size': len(data) if isinstance(data, (list, dict)) else 1,
                'preview_available': True,
                'preview': preview,
                'structure_info': structure_info
            }
        except Exception as e:
            return {'file_type': 'JSON', 'analysis_error': str(e)}
    
    def _analyze_excel(self, content: bytes) -> Dict[str, Any]:
        try:
            import io
            excel_file = pd.ExcelFile(io.BytesIO(content))
            sheet_names = excel_file.sheet_names
            df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_names[0])
            return {
                'file_type': 'Excel',
                'sheet_names': sheet_names,
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns),
                'preview_available': True,
                'preview': df.head(3).to_string(index=False),
                'structure_info': f"Excel file with {len(sheet_names)} sheet(s)"
            }
        except Exception as e:
            return {'file_type': 'Excel', 'analysis_error': str(e)}
    
    def _analyze_text(self, content: bytes) -> Dict[str, Any]:
        try:
            text_content = content.decode('utf-8', errors='replace')
            lines = text_content.splitlines()
            preview = '\n'.join(lines[:10])
            return {
                'file_type': 'Text',
                'lines': len(lines),
                'characters': len(text_content),
                'words': len(text_content.split()),
                'preview_available': True,
                'preview': preview,
                'structure_info': f"Text file with {len(lines)} lines"
            }
        except Exception as e:
            return {'file_type': 'Text', 'analysis_error': str(e)}
    
    def _analyze_sqlite(self, content: bytes) -> Dict[str, Any]:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            os.unlink(temp_path)
            return {
                'file_type': 'SQLite',
                'tables': tables,
                'table_count': len(tables),
                'structure_info': f"SQLite database with {len(tables)} tables",
                'preview_available': False
            }
        except Exception as e:
            return {'file_type': 'SQLite', 'analysis_error': str(e)}
    
    def _analyze_parquet(self, content: bytes) -> Dict[str, Any]:
        try:
            import io
            df = pd.read_parquet(io.BytesIO(content))
            return {
                'file_type': 'Parquet',
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns),
                'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                'preview_available': True,
                'preview': df.head(3).to_string(index=False),
                'structure_info': f"Parquet file with {len(df)} rows"
            }
        except Exception as e:
            return {'file_type': 'Parquet', 'analysis_error': str(e)}
    
    def get_file_summary(self, files: List[Dict[str, Any]]) -> str:
        if not files:
            return "No files uploaded."
        summary_lines = [f"Loaded {len(files)} file(s):"]
        for i, file_info in enumerate(files, 1):
            summary_lines.append(f"\n{i}. {file_info['name']}")
            summary_lines.append(f"   Size: {file_info['size']:,} bytes ({file_info['extension']})")
            if 'error' in file_info:
                summary_lines.append(f"   Error: {file_info['error']}")
            else:
                metadata = file_info.get('metadata', {})
                summary_lines.append(f"   Structure: {metadata.get('structure_info', 'Unknown')}")
                if metadata.get('preview_available') and metadata.get('preview'):
                    preview = metadata['preview'][:200] + ("..." if len(metadata['preview']) > 200 else "")
                    summary_lines.append(f"   Preview:\n   {preview}")
        return '\n'.join(summary_lines)
