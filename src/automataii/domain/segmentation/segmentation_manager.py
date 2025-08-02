"""
Segmentation manager that orchestrates different segmentation strategies.
Provides a unified interface and automatic fallback between strategies.
"""

import logging
import time
from typing import Dict, List, Optional

import numpy as np

from .base_strategy import BaseSegmentationStrategy, SegmentationResult
from .hybrid_ml_strategy import HybridMLStrategy

logger = logging.getLogger(__name__)


class SegmentationManager:
    """
    Manages multiple segmentation strategies with automatic fallback.
    Implements the strategy manager pattern from Gemini consultation.
    """
    
    def __init__(self):
        self.strategies: Dict[str, BaseSegmentationStrategy] = {}
        self.strategy_priority = []  # Ordered list of strategy names by preference
        self.fallback_enabled = True
        self.validation_enabled = True
        
        # Performance and diagnostics
        self.last_result: Optional[SegmentationResult] = None
        self.strategy_performance: Dict[str, List[float]] = {}
        
        # Initialize default strategies
        self._initialize_default_strategies()
    
    def _initialize_default_strategies(self):
        """Initialize the default set of segmentation strategies."""
        try:
            # Add hybrid ML strategy as primary
            ml_strategy = HybridMLStrategy(use_skeleton_refinement=True)
            self.add_strategy("hybrid_ml", ml_strategy, priority=1)
            
            logger.info("Segmentation manager initialized with default strategies")
            
        except Exception as e:
            logger.error(f"Failed to initialize default strategies: {e}")
    
    def add_strategy(
        self, 
        name: str, 
        strategy: BaseSegmentationStrategy, 
        priority: Optional[int] = None
    ):
        """
        Add a segmentation strategy.
        
        Args:
            name: Unique name for the strategy
            strategy: Strategy instance
            priority: Priority order (1 = highest priority)
        """
        self.strategies[name] = strategy
        
        # Update priority list
        if priority is not None:
            # Insert at specified priority position
            if priority <= len(self.strategy_priority):
                self.strategy_priority.insert(priority - 1, name)
            else:
                self.strategy_priority.append(name)
        else:
            # Add at end
            self.strategy_priority.append(name)
        
        # Initialize performance tracking
        self.strategy_performance[name] = []
        
        logger.info(f"Added segmentation strategy '{name}' with priority {priority}")
    
    def remove_strategy(self, name: str):
        """Remove a segmentation strategy."""
        if name in self.strategies:
            del self.strategies[name]
            if name in self.strategy_priority:
                self.strategy_priority.remove(name)
            if name in self.strategy_performance:
                del self.strategy_performance[name]
            logger.info(f"Removed segmentation strategy '{name}'")
    
    def segment(
        self, 
        image: np.ndarray, 
        mask: np.ndarray, 
        skeleton_data: dict,
        strategy_name: Optional[str] = None,
        require_validation: bool = True
    ) -> SegmentationResult:
        """
        Perform character segmentation using the best available strategy.
        
        Args:
            image: Input image as numpy array (H, W, 3)
            mask: Character mask as numpy array (H, W)
            skeleton_data: Skeleton joint positions and hierarchy
            strategy_name: Specific strategy to use (None for auto-selection)
            require_validation: Whether to require validation success
            
        Returns:
            SegmentationResult with masks and metadata
        """
        start_time = time.time()
        
        # Determine strategies to try
        if strategy_name and strategy_name in self.strategies:
            strategies_to_try = [strategy_name]
        else:
            strategies_to_try = self.strategy_priority.copy()
        
        if not strategies_to_try:
            logger.error("No segmentation strategies available")
            return self._create_empty_result(time.time() - start_time)
        
        # Try strategies in order until one succeeds
        for strategy_name in strategies_to_try:
            if strategy_name not in self.strategies:
                continue
                
            try:
                result = self._try_strategy(
                    strategy_name, image, mask, skeleton_data, require_validation
                )
                
                if result.masks:
                    # Success - record performance and return
                    processing_time = time.time() - start_time
                    result.processing_time = processing_time
                    self._record_performance(strategy_name, processing_time)
                    self.last_result = result
                    
                    logger.info(
                        f"Segmentation completed with '{strategy_name}' in {processing_time:.2f}s, "
                        f"found {result.part_count} parts (avg confidence: {result.average_confidence:.2f})"
                    )
                    return result
                    
            except Exception as e:
                logger.warning(f"Strategy '{strategy_name}' failed: {e}")
                continue
        
        # All strategies failed
        logger.error("All segmentation strategies failed")
        total_time = time.time() - start_time
        return self._create_empty_result(total_time)
    
    def _try_strategy(
        self, 
        strategy_name: str, 
        image: np.ndarray, 
        mask: np.ndarray, 
        skeleton_data: dict,
        require_validation: bool
    ) -> SegmentationResult:
        """Try a specific segmentation strategy."""
        strategy = self.strategies[strategy_name]
        
        # Perform segmentation
        strategy_start = time.time()
        masks = strategy.segment(image, mask, skeleton_data)
        strategy_time = time.time() - strategy_start
        
        if not masks:
            return SegmentationResult(
                masks={},
                confidence_scores={},
                strategy_name=strategy_name,
                processing_time=strategy_time
            )
        
        # Get confidence scores
        confidence_scores = strategy.get_confidence_scores()
        
        # Validate if required
        validation_result = None
        if self.validation_enabled:
            validation_result = strategy.validate_segmentation(masks, skeleton_data)
            
            if require_validation and not validation_result[0]:
                logger.debug(f"Strategy '{strategy_name}' failed validation: {validation_result[1]}")
                return SegmentationResult(
                    masks={},
                    confidence_scores=confidence_scores,
                    strategy_name=strategy_name,
                    processing_time=strategy_time,
                    validation_result=validation_result
                )
        
        return SegmentationResult(
            masks=masks,
            confidence_scores=confidence_scores,
            strategy_name=strategy_name,
            processing_time=strategy_time,
            validation_result=validation_result
        )
    
    def _create_empty_result(self, processing_time: float) -> SegmentationResult:
        """Create an empty result for failure cases."""
        return SegmentationResult(
            masks={},
            confidence_scores={},
            strategy_name="none",
            processing_time=processing_time
        )
    
    def _record_performance(self, strategy_name: str, processing_time: float):
        """Record performance metrics for a strategy."""
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = []
        
        performance_list = self.strategy_performance[strategy_name]
        performance_list.append(processing_time)
        
        # Keep only last 100 measurements
        if len(performance_list) > 100:
            performance_list.pop(0)
    
    def get_strategy_stats(self) -> Dict[str, Dict]:
        """Get performance statistics for all strategies."""
        stats = {}
        
        for strategy_name, times in self.strategy_performance.items():
            if times:
                stats[strategy_name] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "last_time": times[-1] if times else 0.0
                }
            else:
                stats[strategy_name] = {
                    "count": 0,
                    "avg_time": 0.0,
                    "min_time": 0.0,
                    "max_time": 0.0,
                    "last_time": 0.0
                }
        
        return stats
    
    def set_strategy_parameters(self, strategy_name: str, **kwargs):
        """Set parameters for a specific strategy."""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].set_parameters(**kwargs)
            logger.info(f"Updated parameters for strategy '{strategy_name}'")
        else:
            logger.warning(f"Strategy '{strategy_name}' not found")
    
    def enable_validation(self, enabled: bool):
        """Enable or disable result validation."""
        self.validation_enabled = enabled
        logger.info(f"Validation {'enabled' if enabled else 'disabled'}")
    
    def enable_fallback(self, enabled: bool):
        """Enable or disable automatic fallback between strategies."""
        self.fallback_enabled = enabled
        logger.info(f"Fallback {'enabled' if enabled else 'disabled'}")
    
    def get_available_strategies(self) -> List[str]:
        """Get list of available strategy names."""
        return list(self.strategies.keys())
    
    def get_last_result(self) -> Optional[SegmentationResult]:
        """Get the result from the last segmentation."""
        return self.last_result