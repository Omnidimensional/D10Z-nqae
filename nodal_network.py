"""
Nodal Network Architecture Module

Implements the tri-modal adaptive nodal network for D10Z architecture.
Supports Fast Path, Quant Path, and Deep Path processing based on
coherence analysis.

Version: v18
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Optional, Any
import numpy as np
from .coherence import CoherenceAnalyzer


class AdaptiveNodalNetwork(nn.Module):
    """
    Adaptive Nodal Network implementing tri-modal processing.
    
    This network automatically routes data through appropriate processing
    paths based on coherence analysis, optimizing for energy efficiency
    while maintaining required precision levels.
    
    Architecture:
        - Slow Path: Full precision FP32 weights (DEEP mode)
        - Fast Path: Rule-based minimal processing (FAST mode)
        - Quant Path: INT8 quantized weights (QUANT mode)
    
    Attributes:
        input_dim: Dimension of input features
        output_dim: Dimension of output
        t_high: Bread path threshold (default: 0.436)
        t_low: Torreja path threshold (default: 0.286)
        q_scale: Quantization scale for INT8 conversion
        
    Example:
        >>> model = AdaptiveNodalNetwork(input_dim=96, output_dim=2)
        >>> data = torch.randn(1, 96)
        >>> phi = 0.5  # Coherence value
        >>> output, mode = model(data, phi)
        >>> print(f"Mode: {mode}")
    """
    
    def __init__(
        self,
        input_dim: int = 96,
        output_dim: int = 2,
        t_high: float = 0.436,
        t_low: float = 0.286,
        q_scale: float = 127.0
    ):
        """
        Initialize adaptive nodal network.
        
        Args:
            input_dim: Input feature dimension
            output_dim: Output dimension
            t_high: Threshold for Bread/FAST path (default: 0.436)
            t_low: Threshold for Torreja/DEEP path (default: 0.286)
            q_scale: Quantization scale factor (default: 127.0 for INT8)
        """
        super().__init__()
        
        # Network dimensions
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.t_high = t_high
        self.t_low = t_low
        self.q_scale = q_scale
        
        # Slow Path (Full Precision)
        self.slow_path = nn.Linear(input_dim, output_dim)
        
        # Fast Path Rules (Dynamically Generated)
        self.fast_path_rules = nn.ParameterDict()
        
        # Initialize analyzer
        self.analyzer = CoherenceAnalyzer()
        
        # Statistics tracking
        self.register_buffer(
            'path_counts', 
            torch.zeros(3, dtype=torch.long)
        )
        
    def forward(
        self, 
        x: torch.Tensor, 
        phi: float
    ) -> Tuple[torch.Tensor, str]:
        """
        Forward pass with automatic path selection.
        
        Args:
            x: Input tensor of shape (batch, input_dim)
            phi: Coherence value in [0, 1]
            
        Returns:
            Tuple of (output tensor, mode string)
        """
        if len(x.shape) == 1:
            x = x.unsqueeze(0)
            
        # Level 1: Fast Path (Energy Optimal)
        if phi >= self.t_high:
            mode = self._fast_path(x, phi)
            
        # Level 2: Quantized Path (Balanced)
        elif phi >= self.t_low:
            mode = self._quant_path(x)
            
        # Level 3: Deep Path (Precision Optimal)
        else:
            mode = self._deep_path(x)
            
        return mode
    
    def _fast_path(self, x: torch.Tensor, phi: float) -> Tuple[torch.Tensor, str]:
        """
        Fast Path processing (Bread Mode).
        
        Uses rule-based processing for maximum energy efficiency.
        Only 1% of standard power consumption.
        """
        # Generate rule key from coherence
        key = f"rule_{str(round(phi, 1)).replace('.', '_')}"
        
        # Create rule if not exists
        if key not in self.fast_path_rules:
            with torch.no_grad():
                self.fast_path_rules[key] = nn.Parameter(
                    torch.randn(self.slow_path.out_features) * 0.01
                )
        
        # Apply rule to mean of input
        output = self.fast_path_rules[key] * x.mean(dim=-1, keepdim=True)
        
        self.path_counts[0] += 1
        return output, "FAST"
    
    def _quant_path(self, x: torch.Tensor) -> Tuple[torch.Tensor, str]:
        """
        Quantized Path processing (Tortilla Mode).
        
        Uses INT8 quantized weights for balanced efficiency.
        25% of standard power consumption.
        """
        # Get full precision weights
        w = self.slow_path.weight.data
        
        # Quantize weights to INT8
        w_range = w.max() - w.min() + 1e-8
        w_q = torch.round(w / w_range * self.q_scale)
        
        # Dequantize
        w_deq = w_q / self.q_scale * w_range
        
        # Compute output
        output = torch.matmul(x, w_deq.t()) + self.slow_path.bias
        
        self.path_counts[1] += 1
        return output, "QUANT"
    
    def _deep_path(self, x: torch.Tensor) -> Tuple[torch.Tensor, str]:
        """
        Deep Path processing (Torreja Mode).
        
        Full precision FP32 processing for maximum accuracy.
        100% of standard power consumption (only when needed).
        """
        output = self.slow_path(x)
        
        self.path_counts[2] += 1
        return output, "DEEP"
    
    def get_path_statistics(self) -> Dict[str, float]:
        """
        Get processing path usage statistics.
        
        Returns:
            Dictionary with path usage percentages
        """
        total = self.path_counts.sum().item()
        if total == 0:
            return {"FAST": 0.0, "QUANT": 0.0, "DEEP": 0.0}
            
        return {
            "FAST": self.path_counts[0].item() / total * 100,
            "QUANT": self.path_counts[1].item() / total * 100,
            "DEEP": self.path_counts[2].item() / total * 100
        }
    
    def reset_statistics(self):
        """Reset path usage statistics."""
        self.path_counts.zero_()


class NodalTriModal(nn.Module):
    """
    Tri-Modal Nodal Network (Alternative Implementation).
    
    Alternative implementation of the tri-modal architecture with
    enhanced features for production deployment.
    """
    
    def __init__(
        self,
        in_f: int,
        out_f: int,
        t_high: float = 0.436,
        t_low: float = 0.286,
        q_scale: float = 127.0
    ):
        """
        Initialize tri-modal network.
        
        Args:
            in_f: Input feature dimension
            out_f: Output feature dimension
            t_high: Bread path threshold
            t_low: Torreja path threshold
            q_scale: Quantization scale
        """
        super().__init__()
        
        self.in_f = in_f
        self.out_f = out_f
        self.t_high = t_high
        self.t_low = t_low
        self.q_scale = q_scale
        
        # Full precision weights
        self.weights_full = nn.Linear(in_f, out_f)
        
        # Rule storage
        self.rules = nn.ParameterDict()
        
    def forward(
        self, 
        x: torch.Tensor, 
        phi: float, 
        t_high: Optional[float] = None,
        t_low: Optional[float] = None
    ) -> Tuple[torch.Tensor, str]:
        """
        Forward pass with tri-modal routing.
        
        Args:
            x: Input tensor
            phi: Coherence value
            t_high: Override threshold (optional)
            t_low: Override threshold (optional)
            
        Returns:
            Tuple of (output, mode string)
        """
        th = t_high if t_high is not None else self.t_high
        tl = t_low if t_low is not None else self.t_low
        
        # Fast Path
        if phi >= th:
            return self._fast_forward(x, phi), "FAST"
            
        # Quant Path
        elif phi >= tl:
            return self._quant_forward(x), "QUANT"
            
        # Deep Path
        else:
            return self._deep_forward(x), "DEEP"
    
    def _fast_forward(self, x: torch.Tensor, phi: float) -> torch.Tensor:
        """Fast path processing."""
        # Format key to avoid PyTorch issues with dots
        rule_key = f"r_{str(round(phi, 1)).replace('.', '')}"
        
        if rule_key not in self.rules:
            with torch.no_grad():
                self.rules[rule_key] = nn.Parameter(
                    torch.randn(self.weights_full.out_features) * 0.1
                )
        
        return self.rules[rule_key] * x.mean(), "FAST"
    
    def _quant_forward(self, x: torch.Tensor) -> torch.Tensor:
        """Quantized path processing."""
        w = self.weights_full.weight.data
        
        # Deterministic quantization
        w_range = w.max() - w.min() + 1e-8
        q_w = torch.round(w / w_range * self.q_scale)
        w_int8 = q_w / self.q_scale * w_range
        
        output = torch.matmul(x, w_int8.t()) + self.weights_full.bias
        
        return output, "QUANT"
    
    def _deep_forward(self, x: torch.Tensor) -> torch.Tensor:
        """Deep path processing."""
        return self.weights_full(x), "DEEP"
    
    def get_energy_savings(self) -> Dict[str, Any]:
        """
        Calculate energy savings metrics.
        
        Returns:
            Dictionary with energy metrics
        """
        stats = self.get_path_statistics()
        
        # Energy costs relative to standard (100%)
        energy_cost = (
            stats["FAST"] * 0.01 +
            stats["QUANT"] * 0.25 +
            stats["DEEP"] * 1.0
        ) / 100.0
        
        return {
            "energy_cost": energy_cost,
            "savings": (1 - energy_cost) * 100,
            "virtual_capacity": 1 / energy_cost if energy_cost > 0 else float('inf')
        }


def create_nodal_network(
    input_dim: int = 96,
    output_dim: int = 2,
    architecture: str = "adaptive"
) -> nn.Module:
    """
    Factory function to create nodal network instances.
    
    Args:
        input_dim: Input feature dimension
        output_dim: Output dimension
        architecture: Architecture type ("adaptive" or "trimodal")
        
    Returns:
        Initialized nodal network module
    """
    if architecture == "adaptive":
        return AdaptiveNodalNetwork(input_dim, output_dim)
    elif architecture == "trimodal":
        return NodalTriModal(input_dim, output_dim)
    else:
        raise ValueError(f"Unknown architecture: {architecture}")
