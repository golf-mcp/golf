"""Unit tests for the ImportTransformer class."""

import ast
from pathlib import Path
import pytest

from golf.core.transformer import ImportTransformer


class TestImportTransformer:
    """Test cases for the ImportTransformer class."""
    
    def test_direct_import_transformation_simple(self, tmp_path):
        """Test that direct imports are converted to from-imports."""
        # Setup paths - component at components/tools/weather.py (2 levels deep)
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        # Create transformer
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        # Test simple import: import config
        node = ast.Import(names=[ast.alias(name="config", asname=None)])
        result = transformer.visit(node)
        
        # Should convert to: from ...config import config
        assert isinstance(result, ast.ImportFrom)
        assert result.module == "config"
        assert result.level == 2  # components/tools/ = 2 levels
        assert len(result.names) == 1
        assert result.names[0].name == "config"
        assert result.names[0].asname is None
        
    def test_direct_import_transformation_with_alias(self, tmp_path):
        """Test that direct imports with aliases are converted correctly."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        # Test import with alias: import config as cfg
        node = ast.Import(names=[ast.alias(name="config", asname="cfg")])
        result = transformer.visit(node)
        
        # Should convert to: from ...config import config as cfg
        assert isinstance(result, ast.ImportFrom)
        assert result.module == "config"
        assert result.level == 2
        assert len(result.names) == 1
        assert result.names[0].name == "config"
        assert result.names[0].asname == "cfg"
        
    def test_dynamic_depth_calculation_shallow(self, tmp_path):
        """Test that import depth is calculated correctly for shallow nesting."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"  # 2 levels deep
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        depth = transformer._calculate_import_depth()
        assert depth == 2  # components/tools/weather.py -> 3 parts - 1 for filename = 2
        
    def test_dynamic_depth_calculation_deep(self, tmp_path):
        """Test that import depth is calculated correctly for deep nesting."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "api" / "v1" / "handler.py"  # 4 levels deep
        original_path = project_root / "tools" / "api" / "v1" / "handler.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        depth = transformer._calculate_import_depth()
        assert depth == 4  # components/tools/api/v1/handler.py -> 5 parts - 1 for filename = 4
        
    def test_mixed_import_styles_in_single_import(self, tmp_path):
        """Test components with both root and non-root imports in same statement."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        # Test: import config, os
        # Should transform config but leave os untouched
        node = ast.Import(names=[
            ast.alias(name="config", asname=None),
            ast.alias(name="os", asname=None)
        ])
        result = transformer.visit(node)
        
        # Should convert config to from-import, returning the from-import for config
        # (the transformer converts first root module found and returns)
        assert isinstance(result, ast.ImportFrom)
        assert result.module == "config"
        assert result.level == 2
        
    def test_from_import_transformation(self, tmp_path):
        """Test that from-imports are transformed with dynamic depth."""
        project_root = tmp_path
        target_path = project_root / "components" / "resources" / "data.py"  # 2 levels deep
        original_path = project_root / "resources" / "data.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"env"}
        )
        
        # Test: from env import API_KEY, TIMEOUT
        node = ast.ImportFrom(
            module="env",
            names=[
                ast.alias(name="API_KEY", asname=None),
                ast.alias(name="TIMEOUT", asname=None)
            ],
            level=0
        )
        result = transformer.visit(node)
        
        # Should convert to: from ...env import API_KEY, TIMEOUT
        assert isinstance(result, ast.ImportFrom)
        assert result.module == "env"
        assert result.level == 2  # Dynamic depth
        assert len(result.names) == 2
        assert result.names[0].name == "API_KEY"
        assert result.names[1].name == "TIMEOUT"
        
    def test_nested_component_imports(self, tmp_path):
        """Test that deeply nested components calculate depth correctly."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "api" / "v1" / "endpoints" / "users.py"  # 5 levels deep
        original_path = project_root / "tools" / "api" / "v1" / "endpoints" / "users.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"database"}
        )
        
        # Test: from database import connection
        node = ast.ImportFrom(
            module="database",
            names=[ast.alias(name="connection", asname=None)],
            level=0
        )
        result = transformer.visit(node)
        
        # Should use level=5 for deeply nested component
        assert isinstance(result, ast.ImportFrom)
        assert result.module == "database"
        assert result.level == 5  # 6 parts - 1 for filename = 5
        
    def test_non_root_imports_unchanged(self, tmp_path):
        """Test that non-root imports are left unchanged."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}  # Only config is root
        )
        
        # Test standard library import
        node = ast.Import(names=[ast.alias(name="os", asname=None)])
        result = transformer.visit(node)
        
        # Should remain unchanged
        assert result is node  # Same object returned
        
    def test_multiple_root_modules(self, tmp_path):
        """Test transformer with multiple root file modules."""
        project_root = tmp_path
        target_path = project_root / "components" / "prompts" / "assistant.py"  # 2 levels deep
        original_path = project_root / "prompts" / "assistant.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config", "env", "database"}
        )
        
        # Test import of each root module
        for module_name in ["config", "env", "database"]:
            node = ast.Import(names=[ast.alias(name=module_name, asname=None)])
            result = transformer.visit(node)
            
            assert isinstance(result, ast.ImportFrom)
            assert result.module == module_name
            assert result.level == 2
            
    def test_import_depth_calculation_fallback(self, tmp_path):
        """Test that depth calculation falls back gracefully on errors."""
        project_root = tmp_path
        # Create a target path that's not under project_root to trigger ValueError
        target_path = Path("/some/other/path/file.py")
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        # Should fallback to level=3
        depth = transformer._calculate_import_depth()
        assert depth == 3
        
    def test_empty_root_file_modules(self, tmp_path):
        """Test transformer behavior with no root file modules."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules=set()  # No root modules
        )
        
        # Test import - should remain unchanged
        node = ast.Import(names=[ast.alias(name="config", asname=None)])
        result = transformer.visit(node)
        
        assert result is node  # Unchanged
        
    def test_from_import_with_relative_level_unchanged(self, tmp_path):
        """Test that existing relative imports are processed by shared file logic."""
        project_root = tmp_path
        target_path = project_root / "components" / "tools" / "weather.py"
        original_path = project_root / "tools" / "weather.py"
        
        transformer = ImportTransformer(
            original_path=original_path,
            target_path=target_path,
            import_map={},
            project_root=project_root,
            root_file_modules={"config"}
        )
        
        # Test existing relative import (should be handled by shared file logic)
        node = ast.ImportFrom(
            module="helpers",
            names=[ast.alias(name="utility", asname=None)],
            level=1  # Relative import
        )
        result = transformer.visit(node)
        
        # Since we don't have import_map entries, it should return unchanged
        # (this tests that the root file transformation doesn't interfere)
        assert result is node