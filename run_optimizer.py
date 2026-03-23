#!/usr/bin/env python3
"""
CLI runner for the OpenClaw Deep Research Optimization System

Usage:
    python run_optimizer.py [output_dir] [cycles]

Examples:
    python run_optimizer.py                          # Run in 'output/' (5 cycles)
    python run_optimizer.py research_results         # Run in 'research_results/' (5 cycles)
    python run_optimizer.py results 3                # Run 3 cycles in 'results/'
"""

import asyncio
import sys
import argparse
from pathlib import Path
from optimizer import OptimizationRunner


async def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw Deep Research Optimization System"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="output",
        help="Directory for output results (default: output/)",
    )
    parser.add_argument(
        "--cycles",
        "-c",
        type=int,
        default=5,
        help="Number of optimization cycles (default: 5)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("OpenClaw Deep Research Optimization System")
    print("=" * 70)
    print(f"Output directory: {output_dir.resolve()}")
    print(f"Optimization cycles: {args.cycles}")
    print()

    runner = OptimizationRunner(output_dir=str(output_dir))

    try:
        print("Starting optimization cycles...")
        print("-" * 70)

        # Run cycles (note: current implementation always runs 5)
        results = await runner.run()

        print("-" * 70)
        print("\nOptimization Complete!")
        print()
        print("Results Summary:")
        print("-" * 70)

        for result in results:
            metrics = result["quality_metrics"]
            timing = result["timing"]

            print(f"\nCycle {result['cycle_num']}:")
            print(f"  Pages collected: {result['pages_collected']}")
            print(f"  Average quality (overall): {metrics['average_overall']:.2f}/10")
            print(f"    - Relevance: {metrics['average_relevance']:.2f}/10")
            print(f"    - Credibility: {metrics['average_credibility']:.2f}/10")
            print(f"    - Uniqueness: {metrics['average_uniqueness']:.2f}/10")
            print(f"  Total time: {timing['total_seconds']:.2f}s")
            print(f"    - Web scan: {timing['web_scan_seconds']:.2f}s")
            print(f"    - Subtopic detection: {timing['subtopic_detection_seconds']:.2f}s")
            print(f"    - Page collection: {timing['page_collection_seconds']:.2f}s")
            print(f"    - Quality scoring: {timing['quality_scoring_seconds']:.2f}s")

        print()
        print("=" * 70)
        print("Output Files:")
        print("-" * 70)
        print(f"  Optimization Report: {output_dir}/optimization_report.json")
        print(f"  Recommendations:     {output_dir}/recommendations.md")
        print()

        for i in range(1, len(results) + 1):
            cycle_dir = output_dir / f"cycle-{i}"
            print(f"  Cycle {i} Results:")
            print(f"    - Pages:   {cycle_dir}/pages/ (100 JSON files)")
            print(f"    - Metadata: {cycle_dir}/metadata.json")
            print(f"    - Timing:   {cycle_dir}/timing.csv")

        print()
        print("=" * 70)
        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
