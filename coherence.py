"""
Coherence Analysis Module

Provides spectral coherence analysis for D10Z Nodal Architecture.
Computes the coherence metric Φ(d) used for path selection and
selective pattern storage.

Version: v18
"""

import numpy as np
from typing import Tuple, Optional
import warnings


class CoherenceAnalyzer:
    """
    Analyzes signal coherence using spectral analysis techniques.
    
    The coherence metric Φ(d) serves as the primary decision criterion
    for the D10Z tri-modal routing system, determining which processing
    path to activate based on signal quality.
    
    Attributes:
        eps: Small constant to prevent division by zero
        window_size: FFT window size for spectral analysis
        
    Example:
        >>> analyzer = CoherenceAnalyzer()
        >>> data = np.random.randn(100)
        >>> phi = analyzer.compute_phi(data)
        >>> print(f"Coherence: {phi:.3f}")
    """
    
    def __init__(self, eps: float = 1e-8):
        """
        Initialize the coherence analyzer.
        
        Args:
            eps: Small constant for numerical stability (default: 1e-8)
        """
        self.eps = eps
        
    def compute_phi(self, data: np.ndarray) -> float:
        """
        Compute coherence metric Φ(d) for input data.
        
        The coherence metric combines energy distribution analysis with
        frequency dominance to produce a value between 0 and 1, where:
        - Φ ≈ 1: High coherence (clean signal)
        - Φ ≈ 0: Low coherence (noisy/chaotic signal)
        
        Args:
            data: Input signal data as numpy array
            
        Returns:
            Coherence metric Φ in range [0, 1]
            
        Mathematical Formulation:
            Φ = tanh( (E_max / E_total) × f_norm × 100 )
            
            Where:
            - E_max: Maximum spectral energy component
            - E_total: Total spectral energy
            - f_norm: Normalized dominant frequency
        """
        # Validate input
        if data is None or len(data) < 10:
            warnings.warn("Input data too short for reliable coherence analysis")
            return 0.0
            
        if not isinstance(data, np.ndarray):
            data = np.array(data, dtype=np.float64)
            
        # Remove NaN and Inf
        data = np.nan_to_num(data, nan=0.0, posinf=1.0, neginf=-1.0)
        
        # Normalize data to zero mean, unit variance
        data_norm = (data - np.mean(data)) / (np.std(data) + self.eps)
        
        # Compute FFT and extract magnitude spectrum
        fft_vals = np.abs(np.fft.fft(data_norm))
        
        # Use first half of spectrum (positive frequencies)
        spectrum = fft_vals[:len(fft_vals) // 2]
        
        # Skip DC component (index 0)
        if np.sum(spectrum[1:]) <= 0:
            return 0.0
            
        # Compute energy distribution metrics
        energy_ratio = np.max(spectrum[1:]) / np.sum(spectrum[1:])
        
        # Find dominant frequency (normalized)
        dominant_idx = np.argmax(spectrum[1:]) + 1
        f_norm = dominant_idx / len(data)
        
        # Compute coherence metric using tanh for smooth [0,1] mapping
        phi = np.tanh(energy_ratio * f_norm * 100)
        
        # Clamp to valid range
        return float(np.clip(phi, 0, 1))
    
    def compute_phi_batch(self, data_batch: np.ndarray) -> np.ndarray:
        """
        Compute coherence for batch of signals.
        
        Args:
            data_batch: Array of shape (n_samples, n_features)
            
        Returns:
            Array of coherence values for each sample
        """
        return np.array([self.compute_phi(sample) for sample in data_batch])
    
    def estimate_coherence_statistics(
        self, 
        data: np.ndarray
    ) -> Tuple[float, float, float]:
        """
        Estimate coherence distribution statistics.
        
        Args:
            data: Input data array
            
        Returns:
            Tuple of (mean, std, max) coherence values
        """
        phis = self.compute_phi_batch(data)
        return np.mean(phis), np.std(phis), np.max(phis)
    
    def classify_signal(self, phi: float) -> str:
        """
        Classify signal based on coherence value.
        
        Args:
            phi: Coherence value in [0, 1]
            
        Returns:
            Classification string: "BREAD", "TORTILLA", or "TORREJA"
        """
        if phi >= 0.436:
            return "BREAD"
        elif phi >= 0.286:
            return "TORTILLA"
        else:
            return "TORREJA"
    
    def get_recommended_path(self, phi: float) -> str:
        """
        Get recommended processing path based on coherence.
        
        Args:
            phi: Coherence value in [0, 1]
            
        Returns:
            Path name: "FAST", "QUANT", or "DEEP"
        """
        return self.classify_signal(phi).replace(
            "BREAD", "FAST"
        ).replace(
            "TORTILLA", "QUANT"
        ).replace(
            "TORREJA", "DEEP"
        )


class SignalCoherenceEstimator:
    """
    Static utility class for signal coherence estimation.
    
    Provides simplified coherence estimation for quick assessments
    without requiring class instantiation.
    """
    
    @staticmethod
    def estimate(data: np.ndarray) -> float:
        """
        Static method for coherence estimation.
        
        Args:
            data: Input signal data
            
        Returns:
            Coherence value in [0, 1]
        """
        analyzer = CoherenceAnalyzer()
        return analyzer.compute_phi(data)
    
    @staticmethod
    def quick_check(data: np.ndarray, threshold: float = 0.436) -> bool:
        """
        Quick coherence check against threshold.
        
        Args:
            data: Input signal data
            threshold: Coherence threshold (default: 0.436)
            
        Returns:
            True if coherence >= threshold
        """
        return SignalCoherenceEstimator.estimate(data) >= threshold


def compute_coherence(data: np.ndarray) -> float:
    """
    Convenience function for coherence computation.
    
    Args:
        data: Input signal data
        
    Returns:
        Coherence metric Φ in [0, 1]
    """
    return CoherenceAnalyzer().compute_phi(data)


def classify_coherence(phi: float) -> str:
    """
    Classify coherence value into path category.
    
    Args:
        phi: Coherence value in [0, 1]
        
    Returns:
        Classification: "BREAD", "TORTILLA", or "TORREJA"
    """
    analyzer = CoherenceAnalyzer()
    return analyzer.classify_signal(phi)
