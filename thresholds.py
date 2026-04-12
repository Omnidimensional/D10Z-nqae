"""
Threshold Configuration Module

Provides threshold management for Pyraclaw Nodal Architecture.
Handles threshold persistence, validation, and optimization.

Version: v18
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
import json
import yaml
import os


@dataclass
class PyraclawThresholds:
    """
    Threshold configuration for Pyraclaw Nodal Architecture.
    
    Stores the critical coherence thresholds that govern path selection
    and system behavior across different operating conditions.
    
    Attributes:
        bread_path: Threshold for Bread/FAST path activation (Φ >= 0.436)
        torreja_path: Threshold for Torreja/DEEP path activation (Φ < 0.286)
        thermal_delta: Operating temperature delta in °C (-67.5)
        scalability_factor: Virtual capacity multiplier (6.42)
        compression_ratio: Target compression ratio (14.9)
        network_relief_factor: Bandwidth expansion factor (8.49)
        energy_savings_target: Target energy savings (0.8443)
    """
    
    bread_path: float = 0.436
    torreja_path: float = 0.286
    
    # Derived parameters
    thermal_delta: float = -67.5
    scalability_factor: float = 6.42
    compression_ratio: float = 14.9
    network_relief_factor: float = 8.49
    energy_savings_target: float = 0.8443
    
    # Additional configuration
    quantization_scale: float = 127.0
    energy_cost_fast: float = 0.01
    energy_cost_quant: float = 0.25
    energy_cost_deep: float = 1.0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert thresholds to dictionary."""
        return {
            "bread_path": self.bread_path,
            "torreja_path": self.torreja_path,
            "thermal_delta": self.thermal_delta,
            "scalability_factor": self.scalability_factor,
            "compression_ratio": self.compression_ratio,
            "network_relief_factor": self.network_relief_factor,
            "energy_savings_target": self.energy_savings_target,
            "quantization_scale": self.quantization_scale,
            "energy_cost_fast": self.energy_cost_fast,
            "energy_cost_quant": self.energy_cost_quant,
            "energy_cost_deep": self.energy_cost_deep,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "PyraclawThresholds":
        """Create thresholds from dictionary."""
        return cls(
            bread_path=data.get("bread_path", 0.436),
            torreja_path=data.get("torreja_path", 0.286),
            thermal_delta=data.get("thermal_delta", -67.5),
            scalability_factor=data.get("scalability_factor", 6.42),
            compression_ratio=data.get("compression_ratio", 14.9),
            network_relief_factor=data.get("network_relief_factor", 8.49),
            energy_savings_target=data.get("energy_savings_target", 0.8443),
            quantization_scale=data.get("quantization_scale", 127.0),
            energy_cost_fast=data.get("energy_cost_fast", 0.01),
            energy_cost_quant=data.get("energy_cost_quant", 0.25),
            energy_cost_deep=data.get("energy_cost_deep", 1.0),
        )
    
    def save(self, filepath: str):
        """Save thresholds to YAML file."""
        with open(filepath, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    @classmethod
    def load(cls, filepath: str) -> "PyraclawThresholds":
        """Load thresholds from YAML file."""
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)
    
    def save_json(self, filepath: str):
        """Save thresholds to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_json(cls, filepath: str) -> "PyraclawThresholds":
        """Load thresholds from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def get_path_for_coherence(self, phi: float) -> str:
        """
        Determine processing path for given coherence.
        
        Args:
            phi: Coherence value in [0, 1]
            
        Returns:
            Path name: "FAST", "QUANT", or "DEEP"
        """
        if phi >= self.bread_path:
            return "FAST"
        elif phi >= self.torreja_path:
            return "QUANT"
        else:
            return "DEEP"
    
    def get_energy_cost_for_path(self, path: str) -> float:
        """
        Get energy cost for processing path.
        
        Args:
            path: Processing path name
            
        Returns:
            Energy cost as fraction of standard (1.0)
        """
        costs = {
            "FAST": self.energy_cost_fast,
            "QUANT": self.energy_cost_quant,
            "DEEP": self.energy_cost_deep,
        }
        return costs.get(path, 1.0)
    
    def calculate_energy_savings(
        self, 
        fast_ratio: float, 
        quant_ratio: float, 
        deep_ratio: float
    ) -> Dict[str, float]:
        """
        Calculate energy savings for given path distribution.
        
        Args:
            fast_ratio: Fraction of processing in FAST mode
            quant_ratio: Fraction of processing in QUANT mode
            deep_ratio: Fraction of processing in DEEP mode
            
        Returns:
            Dictionary with energy metrics
        """
        total_cost = (
            fast_ratio * self.energy_cost_fast +
            quant_ratio * self.energy_cost_quant +
            deep_ratio * self.energy_cost_deep
        )
        
        savings = 1 - total_cost
        
        return {
            "total_energy_cost": total_cost,
            "savings_percent": savings * 100,
            "virtual_capacity": 1 / total_cost if total_cost > 0 else float('inf'),
            "thermal_delta": savings * abs(self.thermal_delta),
        }
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate threshold configuration.
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        if not 0 <= self.bread_path <= 1:
            errors.append("bread_path must be in [0, 1]")
        if not 0 <= self.torreja_path <= 1:
            errors.append("torreja_path must be in [0, 1]")
        if self.bread_path <= self.torreja_path:
            errors.append("bread_path must be > torreja_path")
        if not -100 <= self.thermal_delta <= 0:
            errors.append("thermal_delta should be negative")
        if not 0 < self.scalability_factor <= 100:
            errors.append("scalability_factor must be in (0, 100]")
        if not 1 <= self.compression_ratio <= 1000:
            errors.append("compression_ratio must be in [1, 1000]")
            
        return len(errors) == 0, errors


# Global default configuration
DEFAULT_THRESHOLDS = PyraclawThresholds()


def get_threshold_config(filepath: Optional[str] = None) -> PyraclawThresholds:
    """
    Get threshold configuration from file or defaults.
    
    Args:
        filepath: Optional path to configuration file (YAML or JSON)
        
    Returns:
        PyraclawThresholds configuration object
    """
    if filepath is None:
        return DEFAULT_THRESHOLDS
    
    if not os.path.exists(filepath):
        return DEFAULT_THRESHOLDS
    
    if filepath.endswith('.yaml') or filepath.endswith('.yml'):
        return PyraclawThresholds.load(filepath)
    elif filepath.endswith('.json'):
        return PyraclawThresholds.load_json(filepath)
    else:
        return DEFAULT_THRESHOLDS


def save_default_config(filepath: str):
    """
    Save default configuration to file.
    
    Args:
        filepath: Path to save configuration
    """
    DEFAULT_THRESHOLDS.save(filepath)
