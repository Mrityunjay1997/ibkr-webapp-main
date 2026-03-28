"""
Scanner Configuration Manager

Handles saving, loading, and managing scanner configuration lists.
Stores configurations in JSON format for easy persistence and portability.
"""

import json
import os
from datetime import datetime
from pathlib import Path


class ScannerConfigManager:
    """Manages scanner configuration persistence."""

    def __init__(self, storage_dir="scanner_configs"):
        """
        Initialize scanner config manager.
        
        Args:
            storage_dir: Directory to store scanner configurations
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save_scanner_config(self, config_name: str, form_data: dict) -> dict:
        """
        Save a scanner configuration.
        
        Args:
            config_name: Name of the scanner configuration
            form_data: Dictionary of form field values to save
            
        Returns:
            Dictionary with status, message, and saved config info
        """
        try:
            # Validate config name
            if not config_name or not isinstance(config_name, str):
                return {
                    "success": False,
                    "message": "Invalid configuration name"
                }
            
            # Clean up config name to make it filesystem-safe
            safe_name = "".join(c for c in config_name if c.isalnum() or c in ('-', '_', ' '))
            safe_name = safe_name.strip()
            
            if not safe_name:
                return {
                    "success": False,
                    "message": "Configuration name must contain alphanumeric characters"
                }
            
            # Create config file path
            config_file = self.storage_dir / f"{safe_name}.json"
            
            # Prepare config data
            config_data = {
                "name": config_name,
                "safe_name": safe_name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "form_data": form_data
            }
            
            # Save to JSON file
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            return {
                "success": True,
                "message": f"Scanner config '{config_name}' saved successfully",
                "config_name": config_name,
                "config_file": str(config_file)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error saving configuration: {str(e)}"
            }

    def load_scanner_config(self, config_name: str) -> dict:
        """
        Load a scanner configuration.
        
        Args:
            config_name: Name of the scanner configuration to load
            
        Returns:
            Dictionary with status, message, and form_data if successful
        """
        try:
            # Find config file (support both exact name and safe_name)
            config_file = None
            
            # Try exact filename match first
            potential_file = self.storage_dir / f"{config_name}.json"
            if potential_file.exists():
                config_file = potential_file
            else:
                # Search for config with matching name field
                for f in self.storage_dir.glob("*.json"):
                    try:
                        with open(f, 'r') as cf:
                            data = json.load(cf)
                            if data.get("name") == config_name or data.get("safe_name") == config_name:
                                config_file = f
                                break
                    except:
                        continue
            
            if not config_file or not config_file.exists():
                return {
                    "success": False,
                    "message": f"Configuration '{config_name}' not found"
                }
            
            # Load configuration
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            return {
                "success": True,
                "message": f"Configuration '{config_name}' loaded successfully",
                "config_name": config_data.get("name"),
                "form_data": config_data.get("form_data", {}),
                "created_at": config_data.get("created_at"),
                "updated_at": config_data.get("updated_at")
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error loading configuration: {str(e)}"
            }

    def delete_scanner_config(self, config_name: str) -> dict:
        """
        Delete a scanner configuration.
        
        Args:
            config_name: Name of the scanner configuration to delete
            
        Returns:
            Dictionary with status and message
        """
        try:
            # Find and delete config file
            config_file = None
            
            potential_file = self.storage_dir / f"{config_name}.json"
            if potential_file.exists():
                config_file = potential_file
            else:
                for f in self.storage_dir.glob("*.json"):
                    try:
                        with open(f, 'r') as cf:
                            data = json.load(cf)
                            if data.get("name") == config_name or data.get("safe_name") == config_name:
                                config_file = f
                                break
                    except:
                        continue
            
            if not config_file or not config_file.exists():
                return {
                    "success": False,
                    "message": f"Configuration '{config_name}' not found"
                }
            
            # Delete the file
            os.remove(config_file)
            
            return {
                "success": True,
                "message": f"Configuration '{config_name}' deleted successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error deleting configuration: {str(e)}"
            }

    def list_scanner_configs(self) -> dict:
        """
        List all saved scanner configurations.
        
        Returns:
            Dictionary with status, message, and list of configurations
        """
        try:
            configs = []
            
            for config_file in sorted(self.storage_dir.glob("*.json")):
                try:
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                        configs.append({
                            "name": data.get("name"),
                            "safe_name": data.get("safe_name"),
                            "created_at": data.get("created_at"),
                            "updated_at": data.get("updated_at"),
                            "indicators_enabled": self._count_enabled_indicators(data.get("form_data", {}))
                        })
                except:
                    continue
            
            return {
                "success": True,
                "message": f"Found {len(configs)} scanner configuration(s)",
                "configs": configs
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error listing configurations: {str(e)}",
                "configs": []
            }

    def _count_enabled_indicators(self, form_data: dict) -> int:
        """Count number of enabled indicators in form data."""
        count = 0
        boolean_fields = [
            "booleanFastSMA", "booleanMediumSMA", "booleanSlowSMA",
            "booleanVWAP", "booleanRSI", "booleanFastEMA",
            "booleanSlowEMA", "booleanOBV", "booleanATR",
            "booleanPrevClose", "booleanLowOfDay", "booleanHighOfDay"
        ]
        
        for field in boolean_fields:
            if form_data.get(field) in (True, "True", "true", "on", "1"):
                count += 1
        
        return count

    def duplicate_scanner_config(self, source_name: str, new_name: str) -> dict:
        """
        Duplicate a scanner configuration.
        
        Args:
            source_name: Name of source configuration
            new_name: Name for the new configuration
            
        Returns:
            Dictionary with status and message
        """
        try:
            # Load source config
            load_result = self.load_scanner_config(source_name)
            if not load_result.get("success"):
                return load_result
            
            # Save as new config
            form_data = load_result.get("form_data", {})
            return self.save_scanner_config(new_name, form_data)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error duplicating configuration: {str(e)}"
            }

    def export_all_configs(self, export_file: str) -> dict:
        """
        Export all scanner configurations to a single JSON file.
        
        Args:
            export_file: Path to export file
            
        Returns:
            Dictionary with status and message
        """
        try:
            configs = {}
            
            for config_file in self.storage_dir.glob("*.json"):
                try:
                    with open(config_file, 'r') as f:
                        data = json.load(f)
                        config_name = data.get("name", "unknown")
                        configs[config_name] = data
                except:
                    continue
            
            with open(export_file, 'w') as f:
                json.dump(configs, f, indent=2)
            
            return {
                "success": True,
                "message": f"Exported {len(configs)} configuration(s) to {export_file}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error exporting configurations: {str(e)}"
            }

    def import_configs(self, import_file: str) -> dict:
        """
        Import scanner configurations from a JSON file.
        
        Args:
            import_file: Path to import file
            
        Returns:
            Dictionary with status and message
        """
        try:
            if not os.path.exists(import_file):
                return {
                    "success": False,
                    "message": f"Import file not found: {import_file}"
                }
            
            imported_count = 0
            
            with open(import_file, 'r') as f:
                configs = json.load(f)
            
            for config_name, config_data in configs.items():
                try:
                    form_data = config_data.get("form_data", {})
                    result = self.save_scanner_config(config_name, form_data)
                    if result.get("success"):
                        imported_count += 1
                except:
                    continue
            
            return {
                "success": True,
                "message": f"Imported {imported_count} configuration(s) from {import_file}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error importing configurations: {str(e)}"
            }

    def rename_scanner_config(self, old_name: str, new_name: str) -> dict:
        """
        Rename a scanner configuration.
        
        Args:
            old_name: Current name of configuration
            new_name: New name for configuration
            
        Returns:
            Dictionary with status and message
        """
        try:
            # Load old config
            load_result = self.load_scanner_config(old_name)
            if not load_result.get("success"):
                return load_result
            
            form_data = load_result.get("form_data", {})
            
            # Delete old config
            delete_result = self.delete_scanner_config(old_name)
            if not delete_result.get("success"):
                return delete_result
            
            # Save with new name
            return self.save_scanner_config(new_name, form_data)
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error renaming configuration: {str(e)}"
            }
