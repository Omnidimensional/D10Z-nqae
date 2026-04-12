"""
Basic Usage Example for Pyraclaw Nodal Architecture

This example demonstrates the fundamental usage of the Pyraclaw
Universal Nodal Architecture including coherence analysis and
tri-modal path selection.

Version: v18
"""

import numpy as np
from pyraclaw.core import (
    AdaptiveNodalNetwork,
    CoherenceAnalyzer,
    PyraclawThresholds,
    BREAD_PATH_THRESHOLD,
    TORREJA_PATH_THRESHOLD
)


def example_basic_coherence():
    """Example: Basic coherence analysis."""
    print("=" * 60)
    print("Pyraclaw Example: Basic Coherence Analysis")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = CoherenceAnalyzer()
    
    # Generate test signals
    clean_signal = np.sin(np.linspace(0, 10 * np.pi, 100))
    noisy_signal = clean_signal + np.random.randn(100) * 0.5
    
    # Compute coherence
    phi_clean = analyzer.compute_phi(clean_signal)
    phi_noisy = analyzer.compute_phi(noisy_signal)
    
    print(f"\nClean Signal Coherence: {phi_clean:.4f}")
    print(f"Noisy Signal Coherence: {phi_noisy:.4f}")
    print(f"\nRecommended Path (Clean): {analyzer.get_recommended_path(phi_clean)}")
    print(f"Recommended Path (Noisy): {analyzer.get_recommended_path(phi_noisy)}")


def example_tri_modal_network():
    """Example: Tri-modal network processing."""
    print("\n" + "=" * 60)
    print("Pyraclaw Example: Tri-Modal Network Processing")
    print("=" * 60)
    
    # Initialize network
    model = AdaptiveNodalNetwork(input_dim=96, output_dim=2)
    
    # Generate test data
    test_data = torch.randn(1, 96)
    
    # Test with different coherence values
    coherence_values = [0.5, 0.35, 0.2]
    
    print("\nPath Selection Results:")
    print("-" * 40)
    
    for phi in coherence_values:
        output, mode = model(test_data, phi)
        print(f"Φ = {phi:.3f} → Mode: {mode}")
        
    # Get path statistics
    stats = model.get_path_statistics()
    print(f"\nPath Statistics: {stats}")


def example_energy_savings():
    """Example: Calculate energy savings."""
    print("\n" + "=" * 60)
    print("Pyraclaw Example: Energy Savings Calculation")
    print("=" * 60)
    
    # Initialize thresholds
    thresholds = PyraclawThresholds()
    
    # Simulated path distribution (70% FAST, 20% QUANT, 10% DEEP)
    fast_ratio = 0.70
    quant_ratio = 0.20
    deep_ratio = 0.10
    
    # Calculate savings
    savings = thresholds.calculate_energy_savings(
        fast_ratio, quant_ratio, deep_ratio
    )
    
    print(f"\nPath Distribution:")
    print(f"  FAST Path:  {fast_ratio * 100:.1f}%")
    print(f"  QUANT Path: {quant_ratio * 100:.1f}%")
    print(f"  DEEP Path:  {deep_ratio * 100:.1f}%")
    print(f"\nResults:")
    print(f"  Total Energy Cost: {savings['total_energy_cost'] * 100:.2f}%")
    print(f"  Energy Savings:    {savings['savings_percent']:.2f}%")
    print(f"  Virtual Capacity:  {savings['virtual_capacity']:.2f}x")
    print(f"  Thermal Delta:     {savings['thermal_delta']:.1f}°C")


def example_threshold_config():
    """Example: Threshold configuration management."""
    print("\n" + "=" * 60)
    print("Pyraclaw Example: Threshold Configuration")
    print("=" * 60)
    
    # Get default thresholds
    thresholds = PyraclawThresholds()
    
    print(f"\nDefault Thresholds:")
    print(f"  Bread Path:   {thresholds.bread_path}")
    print(f"  Torreja Path: {thresholds.torreja_path}")
    print(f"  Thermal Delta: {thresholds.thermal_delta}°C")
    print(f"  Scalability Factor: {thresholds.scalability_factor}x")
    print(f"  Compression Ratio: {thresholds.compression_ratio}x")
    
    # Validate configuration
    is_valid, errors = thresholds.validate()
    print(f"\nConfiguration Valid: {is_valid}")
    if errors:
        print(f"Errors: {errors}")
    
    # Path for coherence
    for phi in [0.5, 0.35, 0.2]:
        path = thresholds.get_path_for_coherence(phi)
        cost = thresholds.get_energy_cost_for_path(path)
        print(f"\nΦ = {phi:.3f} → Path: {path} → Energy Cost: {cost * 100:.1f}%")


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("# Pyraclaw Universal Nodal Architecture - Examples")
    print("# Version: v18 | Published: January 23, 2026")
    print("#" * 60 + "\n")
    
    # Import torch
    import torch
    
    # Run examples
    example_basic_coherence()
    example_tri_modal_network()
    example_energy_savings()
    example_threshold_config()
    
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
