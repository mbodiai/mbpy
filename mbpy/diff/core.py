from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import shutil
import difflib

@dataclass
class DiffContext:
    before: List[str]
    after: List[str]
    is_folded: bool = False
    is_selected: bool = False

    def toggle_fold(self):
        self.is_folded = not self.is_folded
    
    def toggle_selection(self):
        self.is_selected = not self.is_selected

@dataclass
class DiffBlock:
    header: str
    changes: List[str]
    context: DiffContext
    is_folded: bool = False
    is_selected: bool = False
    
    @property
    def description(self) -> str:
        """Generate a meaningful description from the changes."""
        for change in self.changes:
            if change.startswith('+'):
                line = change[1:].strip()  # Fixed typo: changed trip() to strip()
                if line and not line.isspace():
                    return line[:60] + ('...' if len(line) > 60 else '')
        return self.header.strip()
    
    @property
    def has_changes(self) -> bool:
        return any(line.startswith(('+', '-')) for line in self.changes)

class DiffParser:
    @staticmethod
    def parse_blocks(diff_lines: List[str]) -> List[DiffBlock]:
        blocks = []
        current = {'header': None, 'changes': [], 'context': {'before': [], 'after': []}}
        
        for line in diff_lines:
            if line.startswith('@@'):
                if current['header']:
                    blocks.append(DiffBlock(
                        header=current['header'],
                        changes=current['changes'],
                        context=DiffContext(
                            before=current['context']['before'],
                            after=current['context']['after']
                        )
                    ))
                    current = {'header': line, 'changes': [], 'context': {'before': [], 'after': []}}
                else:
                    current['header'] = line
            elif line.startswith(('+', '-')):
                current['changes'].append(line)
            else:
                target = current['context']['before'] if not current['changes'] else current['context']['after']
                target.append(line)
        
        if current['header']:
            blocks.append(DiffBlock(
                header=current['header'],
                changes=current['changes'],
                context=DiffContext(
                    before=current['context']['before'],
                    after=current['context']['after']
                )
            ))
        
        return blocks

class DiffManager:
    def __init__(self, file1: str, file2: str):
        self.file1 = file1
        self.file2 = file2
        self.blocks: List[DiffBlock] = []
    
    def backup_files(self) -> tuple[str, str]:
        """Create backups of both files."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup1 = f"{self.file1}.{timestamp}.bak"
        backup2 = f"{self.file2}.{timestamp}.bak"
        
        shutil.copy2(self.file1, backup1)
        shutil.copy2(self.file2, backup2)
        return backup1, backup2
    
    def generate_diff(self, context_lines: int = 3) -> List[DiffBlock]:
        """Generate diff blocks between the two files."""
        with open(self.file1) as f1, open(self.file2) as f2:
            diff = list(difflib.unified_diff(
                f1.readlines(),
                f2.readlines(),
                fromfile=self.file1,
                tofile=self.file2,
                n=context_lines
            ))
        
        self.blocks = DiffParser.parse_blocks(diff)
        return self.blocks
    
    def get_selected_changes(self) -> List[str]:
        """Get all selected changes."""
        return [
            change
            for block in self.blocks
            if block.is_selected
            for change in block.changes
        ]
