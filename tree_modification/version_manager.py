"""
Version Manager - Manages versioned saves of XML trees.

Creates versioned copies of trees (tree_v1.xml, tree_v2.xml, etc.)
and tracks version history.
"""

import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
import xml.etree.ElementTree as ET

from .base import TreeVersion


logger = logging.getLogger(__name__)


class VersionManager:
    """
    Manages versioned saves of XML trees.
    
    Creates versioned copies with pattern: {basename}_v{N}.xml
    Maintains a version history metadata file.
    """
    
    VERSION_PATTERN = re.compile(r"_v(\d+)\.xml$")
    
    def __init__(self, base_directory: Path = None):
        """
        Initialize the version manager.
        
        Args:
            base_directory: Directory for versioned files. 
                          If None, uses the original file's directory.
        """
        self.base_directory = base_directory
    
    def save_version(
        self,
        tree: ET.ElementTree,
        original_path: Path,
        operation: str,
        changes: dict = None,
        custom_name: str = None
    ) -> TreeVersion:
        """
        Save a new version of the tree.
        
        Args:
            tree: The XML tree to save
            original_path: Path to the original file
            operation: Description of the operation that triggered this version
            changes: Summary of changes made
            custom_name: Optional custom filename (without .xml extension).
                        If provided, skips versioning and uses this name directly.
            
        Returns:
            TreeVersion with version info
        """
        original_path = Path(original_path)
        
        # Determine base directory
        if self.base_directory:
            output_dir = self.base_directory
        else:
            output_dir = original_path.parent
        
        # Use custom name if provided, otherwise use versioning
        if custom_name:
            versioned_filename = f"{custom_name}.xml"
            versioned_path = output_dir / versioned_filename
            next_version = 0  # No version tracking for custom names
            base_name = custom_name
        else:
            # Get the base name without any version suffix
            base_name = self._get_base_name(original_path)
            
            # Find next version number
            next_version = self._get_next_version(output_dir, base_name)
            
            # Create versioned filename
            versioned_filename = f"{base_name}_v{next_version}.xml"
            versioned_path = output_dir / versioned_filename
        
        # Save the tree
        try:
            # Use indent for readable output (Python 3.9+)
            try:
                ET.indent(tree.getroot())
            except AttributeError:
                # Fallback for older Python versions
                self._indent_element(tree.getroot())
            
            tree.write(versioned_path, encoding="unicode", xml_declaration=True)
            
            timestamp = datetime.now().isoformat()
            
            version_info = TreeVersion(
                version=next_version,
                path=str(versioned_path),
                timestamp=timestamp,
                operation=operation,
                changes=changes or {}
            )
            
            # Update version history (skip for custom names - used in eval mode)
            if not custom_name:
                self._update_history(output_dir, base_name, version_info)
            
            logger.info(f"Saved version {next_version} to {versioned_path}")
            print(f"📁 Tree saved: {versioned_path}")
            
            return version_info
            
        except Exception as e:
            logger.error(f"Error saving version: {e}")
            raise
    
    def get_latest_version(
        self,
        original_path: Path
    ) -> Optional[TreeVersion]:
        """
        Get information about the latest version.
        
        Args:
            original_path: Path to the original file
            
        Returns:
            TreeVersion for the latest version, or None if no versions exist
        """
        original_path = Path(original_path)
        
        if self.base_directory:
            output_dir = self.base_directory
        else:
            output_dir = original_path.parent
        
        base_name = self._get_base_name(original_path)
        history = self._load_history(output_dir, base_name)
        
        if history and "versions" in history and history["versions"]:
            latest = history["versions"][-1]
            return TreeVersion(**latest)
        
        return None
    
    def get_version_history(
        self,
        original_path: Path
    ) -> List[TreeVersion]:
        """
        Get the full version history.
        
        Args:
            original_path: Path to the original file
            
        Returns:
            List of TreeVersion objects
        """
        original_path = Path(original_path)
        
        if self.base_directory:
            output_dir = self.base_directory
        else:
            output_dir = original_path.parent
        
        base_name = self._get_base_name(original_path)
        history = self._load_history(output_dir, base_name)
        
        if history and "versions" in history:
            return [TreeVersion(**v) for v in history["versions"]]
        
        return []
    
    def load_version(
        self,
        original_path: Path,
        version: int
    ) -> Optional[ET.ElementTree]:
        """
        Load a specific version of the tree.
        
        Args:
            original_path: Path to the original file
            version: Version number to load
            
        Returns:
            ElementTree for the specified version, or None if not found
        """
        original_path = Path(original_path)
        
        if self.base_directory:
            output_dir = self.base_directory
        else:
            output_dir = original_path.parent
        
        base_name = self._get_base_name(original_path)
        versioned_path = output_dir / f"{base_name}_v{version}.xml"
        
        if versioned_path.exists():
            return ET.parse(versioned_path)
        
        return None
    
    def _get_base_name(self, path: Path) -> str:
        """
        Extract the base name without version suffix.
        
        Examples:
            travel_memory_5day.xml -> travel_memory_5day
            travel_memory_5day_v3.xml -> travel_memory_5day
        """
        name = path.stem  # Without .xml
        
        # Remove version suffix if present
        match = self.VERSION_PATTERN.search(path.name)
        if match:
            name = name[:name.rfind("_v")]
        
        return name
    
    def _get_next_version(self, directory: Path, base_name: str) -> int:
        """Find the next version number."""
        max_version = 0
        
        for file in directory.glob(f"{base_name}_v*.xml"):
            match = self.VERSION_PATTERN.search(file.name)
            if match:
                version = int(match.group(1))
                max_version = max(max_version, version)
        
        return max_version + 1
    
    def _get_history_path(self, directory: Path, base_name: str) -> Path:
        """Get path to the version history file."""
        return directory / f"{base_name}_versions.json"
    
    def _load_history(self, directory: Path, base_name: str) -> dict:
        """Load version history from file."""
        history_path = self._get_history_path(directory, base_name)
        
        if history_path.exists():
            with open(history_path, "r") as f:
                return json.load(f)
        
        return {"base_name": base_name, "versions": []}
    
    def _update_history(
        self,
        directory: Path,
        base_name: str,
        version_info: TreeVersion
    ):
        """Update the version history file."""
        history = self._load_history(directory, base_name)
        history["versions"].append(version_info.to_dict())
        
        history_path = self._get_history_path(directory, base_name)
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)
    
    def _indent_element(self, elem: ET.Element, level: int = 0):
        """
        Add indentation to XML element (fallback for Python < 3.9).
        """
        indent = "\n" + "  " * level
        
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_element(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
