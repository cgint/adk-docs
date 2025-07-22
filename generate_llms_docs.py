#!/usr/bin/env python3
"""
Script to generate clean, language-specific documentation files for ADK.

Usage:
    uv run generate_llms_docs.py

Generates:
    - llms-core.txt: Language-agnostic concepts and overview
    - llms-python.txt: Python-specific documentation 
    - llms-java.txt: Java-specific documentation

/// script
dependencies = [
    "beautifulsoup4>=4.12.0",
    "markdownify>=0.11.6",
]
///
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
import logging

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError:
    print("Installing required dependencies...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "markdownify"])
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class DocumentationGenerator:
    def __init__(self, docs_root: str = "docs"):
        self.docs_root = Path(docs_root)
        self.base_content = self._load_base_content()
        
    def _load_base_content(self) -> str:
        """Load the existing good quality llms.txt as our base."""
        try:
            with open("llms.txt", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("llms.txt not found, starting with empty base")
            return ""
    
    def _clean_html_content(self, html_content: str) -> str:
        """Convert HTML content to clean markdown, preserving structure."""
        if "404 - Not found" in html_content or len(html_content) < 100:
            return ""
            
        # Convert HTML to markdown using markdownify
        # Use simple configuration to avoid parameter conflicts
        markdown_content = md(
            html_content,
            heading_style="ATX",  # Use # ## ### style headers
            bullets="-",          # Use - for bullet points
            strip=['script', 'style', 'nav', 'header', 'footer']  # Remove these tags entirely
        )
        
        if not markdown_content:
            return ""
            
        # Clean up the markdown
        # Remove excessive whitespace
        markdown_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', markdown_content)
        
        # Remove navigation noise
        markdown_content = re.sub(r'Back to top.*?(?=\n|$)', '', markdown_content, flags=re.IGNORECASE)
        markdown_content = re.sub(r'Toggle.*?theme.*?(?=\n|$)', '', markdown_content, flags=re.IGNORECASE)
        markdown_content = re.sub(r'View this page.*?(?=\n|$)', '', markdown_content, flags=re.IGNORECASE)
        
        # Clean up anchor symbols
        markdown_content = re.sub(r'¶\s*$', '', markdown_content, flags=re.MULTILINE)
        
        return markdown_content.strip()
    
    def _extract_file_content(self, file_path: Path) -> Dict[str, str]:
        """Extract content from any file type."""
        try:
            # Simple path string for relative path
            relative_path = str(file_path).replace(str(Path.cwd()) + "/", "")
            
            # Handle different file types
            if file_path.suffix == '.md':
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Remove YAML frontmatter
                content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
                
            elif file_path.suffix == '.html':
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                content = self._clean_html_content(html_content)
                if not content or len(content) < 100:  # Skip very short content
                    return {}
                    
            elif file_path.suffix in ['.py', '.java', '.txt', '.yaml', '.yml', '.json']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                return {}  # Skip unsupported file types
                
            # Extract title from content or filename
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1)
            elif file_path.suffix == '.html':
                soup = BeautifulSoup(content if file_path.suffix != '.html' else 
                                   open(file_path, 'r', encoding='utf-8').read(), 'html.parser')
                title_tag = soup.find('title') or soup.find('h1')
                title = title_tag.get_text().strip() if title_tag else file_path.stem
            else:
                title = file_path.stem.replace('-', ' ').replace('_', ' ').title()
                
            return {
                'title': title,
                'content': content.strip(),
                'path': str(file_path),
                'relative_path': relative_path,
                'type': file_path.suffix
            }
        except Exception as e:
            logger.warning(f"Failed to process {file_path}: {e}")
            return {}
    
    def _is_python_specific(self, content: str, path: str) -> bool:
        """Determine if content is Python-specific based on path only."""
        path_lower = path.lower()
        
        # Only Python API reference documentation
        return 'docs/api-reference/python/' in path_lower or '/docs/api-reference/python/' in path_lower
    
    def _is_java_specific(self, content: str, path: str) -> bool:
        """Determine if content is Java-specific based on path only."""
        path_lower = path.lower()
        
        # Only Java API reference documentation, and specifically only index-all.html
        return ('docs/api-reference/java/' in path_lower or '/docs/api-reference/java/' in path_lower) and 'index-all.html' in path_lower
    
    def _organize_content_by_directory(self) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
        """Organize all content by directory structure and language."""
        content = {
            'core': {},
            'python': {},
            'java': {}
        }
        
        # Process all files recursively
        logger.info("Processing all files...")
        
        # Process docs directory only
        if self.docs_root.exists():
            for file_path in self.docs_root.rglob('*'):
                if file_path.is_file() and not any(skip in str(file_path) for skip in 
                                                 ['.DS_Store', '__pycache__']):
                    
                    # Skip navigation/index files in api-reference
                    if 'api-reference/index.md' in str(file_path):
                        continue
                    
                    # Skip all Java API reference files except index-all.html
                    if ('api-reference/java/' in str(file_path) and 
                        'index-all.html' not in str(file_path)):
                        continue
                    
                    file_content = self._extract_file_content(file_path)
                    if not file_content:
                        continue
                        
                    # Get directory path for organization
                    dir_path = str(file_path.parent)
                    
                    # Categorize content based on path only
                    path_str = str(file_path)
                    content_str = file_content['content']
                    
                    if self._is_python_specific(content_str, path_str):
                        if dir_path not in content['python']:
                            content['python'][dir_path] = []
                        content['python'][dir_path].append(file_content)
                    elif self._is_java_specific(content_str, path_str):
                        if dir_path not in content['java']:
                            content['java'][dir_path] = []
                        content['java'][dir_path].append(file_content)
                    else:
                        # Everything else in docs goes to core
                        if dir_path not in content['core']:
                            content['core'][dir_path] = []
                        content['core'][dir_path].append(file_content)
        
        return content
    
    def _generate_documentation_by_structure(self, content: Dict, lang: str) -> str:
        """Generate documentation organized by directory structure."""
        doc = []
        
        if lang == 'core':
            doc.append("# Agent Development Kit (ADK) - Core Concepts\n")
            doc.append("*Language-agnostic documentation extracted from repository*\n")
            
            # Add base content summary if available
            if self.base_content:
                doc.append("\n## Overview (from existing llms.txt)\n")
                # Just add first part of base content
                base_lines = self.base_content.split('\n')[:50]  # First 50 lines
                doc.extend(base_lines)
                doc.append("\n---\n")
                
        elif lang == 'python':
            doc.append("# Agent Development Kit (ADK) - Python\n")
            doc.append("*Python-specific documentation and examples from repository*\n")
        else:
            doc.append("# Agent Development Kit (ADK) - Java\n")
            doc.append("*Java-specific documentation and examples from repository*\n")
        
        # Organize by directory
        lang_content = content[lang]
        
        if not lang_content:
            doc.append(f"\n*No {lang}-specific content found in repository*\n")
            return '\n'.join(doc)
        
        for dir_path in sorted(lang_content.keys()):
            files = lang_content[dir_path]
            if not files:
                continue
                
            # Clean up directory path for display
            display_dir = dir_path.replace(str(Path.cwd()), "").lstrip("/")
            doc.append(f"\n## Directory: {display_dir}\n")
            
            for file_info in sorted(files, key=lambda x: x['relative_path']):
                doc.append(f"\n### {file_info['title']}\n")
                doc.append(f"*File: {file_info['relative_path']}*\n")
                
                # Add content with appropriate formatting
                file_content = file_info['content']
                
                doc.append(file_content)
                
                doc.append("\n---\n")
        
        return '\n'.join(doc)
    
    def generate_all_docs(self):
        """Generate all documentation files including combined versions."""
        logger.info("Starting documentation generation...")
        
        # Organize all content by directory structure
        content = self._organize_content_by_directory()
        
        # Generate individual files
        logger.info("Generating core documentation...")
        core_doc = self._generate_documentation_by_structure(content, 'core')
        with open("llms-core.txt", "w", encoding="utf-8") as f:
            f.write(core_doc)
        
        logger.info("Generating Python documentation...")
        python_doc = self._generate_documentation_by_structure(content, 'python')
        with open("llms-python.txt", "w", encoding="utf-8") as f:
            f.write(python_doc)
        
        logger.info("Generating Java documentation...")
        java_doc = self._generate_documentation_by_structure(content, 'java')
        with open("llms-java.txt", "w", encoding="utf-8") as f:
            f.write(java_doc)
        
        # Generate combined files
        logger.info("Generating combined Python documentation...")
        python_full_doc = core_doc + "\n\n" + "="*50 + "\n" + "="*50 + "\n\n" + python_doc
        with open("llms-python-full.txt", "w", encoding="utf-8") as f:
            f.write(python_full_doc)
        
        logger.info("Generating combined Java documentation...")
        java_full_doc = core_doc + "\n\n" + "="*50 + "\n" + "="*50 + "\n\n" + java_doc
        with open("llms-java-full.txt", "w", encoding="utf-8") as f:
            f.write(java_full_doc)
        
        # Print statistics
        logger.info(f"Generated files:")
        logger.info(f"  llms-core.txt: {len(core_doc):,} characters")
        logger.info(f"  llms-python.txt: {len(python_doc):,} characters")
        logger.info(f"  llms-java.txt: {len(java_doc):,} characters")
        logger.info(f"  llms-python-full.txt: {len(python_full_doc):,} characters")
        logger.info(f"  llms-java-full.txt: {len(java_full_doc):,} characters")
        
        # Print directory statistics
        for lang in ['core', 'python', 'java']:
            dirs = list(content[lang].keys())
            logger.info(f"  {lang}: {len(dirs)} directories processed")
        
        logger.info("Documentation generation completed successfully!")

def main():
    """Main entry point."""
    generator = DocumentationGenerator()
    generator.generate_all_docs()

if __name__ == "__main__":
    main() 