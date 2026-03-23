"""
Test suite for deep research optimizer (TDD - RED Phase)
Tests auto-subtopic detection, quality scoring, and optimization cycles
"""

import pytest
import json
import os
import tempfile
import asyncio
from pathlib import Path
from optimizer import (
    SubtopicDetector,
    QualityScorer,
    ResearchCycle,
    OptimizationRunner,
)


class TestSubtopicDetection:
    """RED Phase: Test auto-detection of subtopics from web scan results"""

    @pytest.mark.asyncio
    async def test_detects_five_subtopics_from_web_results(self):
        """Test that SubtopicDetector extracts 5 subtopics from web search results"""
        web_results = [
            {"title": "OpenClaw Agent Architecture", "snippet": "How OpenClaw agents work with multi-agent systems"},
            {"title": "OpenClaw Benchmark Results", "snippet": "Performance metrics for OpenClaw agents"},
            {"title": "OpenClaw Integration Guide", "snippet": "Integrating OpenClaw into your applications"},
            {"title": "OpenClaw vs Other Agents", "snippet": "Comparison with Claude agents and other tools"},
            {"title": "OpenClaw API Reference", "snippet": "Complete API documentation for OpenClaw"},
            {"title": "Real-world OpenClaw Examples", "snippet": "Production deployments using OpenClaw"},
        ]

        detector = SubtopicDetector()
        subtopics = await detector.detect(web_results, num_subtopics=5)

        assert len(subtopics) == 5
        assert all(isinstance(s, dict) for s in subtopics)
        assert all("name" in s and "query" in s for s in subtopics)

    @pytest.mark.asyncio
    async def test_subtopics_are_distinct(self):
        """Test that detected subtopics are distinct and non-overlapping"""
        web_results = [
            {"title": f"Result {i}", "snippet": f"Description {i}"} for i in range(20)
        ]

        detector = SubtopicDetector()
        subtopics = await detector.detect(web_results, num_subtopics=5)

        names = [s["name"] for s in subtopics]
        queries = [s["query"] for s in subtopics]

        # All names should be unique
        assert len(names) == len(set(names))
        # All queries should be unique
        assert len(queries) == len(set(queries))


class TestQualityScoring:
    """RED Phase: Test quality scoring of web pages"""

    def test_handles_none_title_in_score_relevance(self):
        """CRITICAL 1: Test that score_relevance handles None title without crashing"""
        scorer = QualityScorer()

        page = {
            "title": None,
            "content": "Some content about OpenClaw",
            "url": "https://example.com",
        }

        # Should not crash with AttributeError
        score = scorer.score_relevance(page)
        assert 1 <= score <= 10

    def test_handles_none_content_in_score_relevance(self):
        """CRITICAL 1: Test that score_relevance handles None content without crashing"""
        scorer = QualityScorer()

        page = {
            "title": "OpenClaw Page",
            "content": None,
            "url": "https://example.com",
        }

        # Should not crash with AttributeError
        score = scorer.score_relevance(page)
        assert 1 <= score <= 10

    def test_handles_none_url_in_score_relevance(self):
        """CRITICAL 1: Test that score_relevance handles None url without crashing"""
        scorer = QualityScorer()

        page = {
            "title": "OpenClaw Page",
            "content": "Some content",
            "url": None,
        }

        # Should not crash with AttributeError
        score = scorer.score_relevance(page)
        assert 1 <= score <= 10

    def test_handles_none_in_score_credibility(self):
        """CRITICAL 1: Test that score_credibility handles None values without crashing"""
        scorer = QualityScorer()

        page = {
            "url": None,
            "source_type": None,
            "title": None,
        }

        # Should not crash with AttributeError
        score = scorer.score_credibility(page)
        assert 1 <= score <= 10

    def test_handles_none_in_score_uniqueness(self):
        """CRITICAL 1: Test that score_uniqueness handles None values without crashing"""
        scorer = QualityScorer()

        page = {
            "title": None,
            "content": None,
        }

        other_page = {
            "title": "Some Title",
            "content": "Some content",
        }

        # Should not crash with AttributeError
        score = scorer.score_uniqueness(page, [other_page])
        assert 1 <= score <= 10

    def test_scores_page_relevance_1_to_10(self):
        """Test that relevance scores are between 1-10"""
        scorer = QualityScorer()

        page = {
            "title": "OpenClaw Agent Framework",
            "content": "OpenClaw is an agent framework for building autonomous systems...",
            "url": "https://docs.openclaw.io",
        }

        score = scorer.score_relevance(page)

        assert 1 <= score <= 10
        assert isinstance(score, (int, float))

    def test_scores_credibility_based_on_source(self):
        """Test that credibility scoring varies by source type"""
        scorer = QualityScorer()

        # Official documentation should score higher
        official = {
            "url": "https://docs.openclaw.io",
            "source_type": "documentation",
            "title": "OpenClaw API",
        }
        official_score = scorer.score_credibility(official)

        # Blog post should score lower
        blog = {
            "url": "https://myblog.com/openclaw-tips",
            "source_type": "blog",
            "title": "My OpenClaw Tips",
        }
        blog_score = scorer.score_credibility(blog)

        assert 1 <= official_score <= 10
        assert 1 <= blog_score <= 10
        assert official_score > blog_score

    def test_scores_uniqueness_1_to_10(self):
        """Test that uniqueness is scored 1-10"""
        scorer = QualityScorer()

        page1 = {"title": "Unique Page A", "content": "Unique content about topic A"}
        page2 = {"title": "Unique Page B", "content": "Unique content about topic B"}

        score1 = scorer.score_uniqueness(page1, [])
        score2 = scorer.score_uniqueness(page2, [page1])

        assert 1 <= score1 <= 10
        assert 1 <= score2 <= 10

    def test_overall_quality_is_average_of_three_metrics(self):
        """Test that overall quality is the average of relevance, credibility, uniqueness"""
        scorer = QualityScorer()

        page = {
            "title": "OpenClaw Documentation",
            "content": "Official docs...",
            "url": "https://docs.openclaw.io",
            "source_type": "documentation",
        }

        relevance = scorer.score_relevance(page)
        credibility = scorer.score_credibility(page)
        uniqueness = scorer.score_uniqueness(page, [])

        overall = scorer.score_overall(page, [])

        expected_overall = (relevance + credibility + uniqueness) / 3
        assert abs(overall - expected_overall) < 0.01


class TestResearchCycle:
    """RED Phase: Test a single research cycle"""

    @pytest.mark.asyncio
    async def test_handles_file_write_error_in_save_pages(self):
        """CRITICAL 3: Test that file I/O errors in _save_pages are caught"""
        # Use a read-only directory to force permission error
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            pages_dir = cycle.cycle_dir / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)

            # Make directory read-only to trigger write error
            os.chmod(pages_dir, 0o444)

            try:
                from optimizer import PageData

                pages = [
                    PageData(
                        url="https://example.com/1",
                        title="Test Page",
                        content="Test content",
                        source_type="blog",
                        relevance_score=5.0,
                        credibility_score=5.0,
                        uniqueness_score=5.0,
                        overall_quality=5.0,
                    )
                ]

                # Should not crash with unhandled exception
                cycle._save_pages(pages_dir, pages)
            finally:
                # Restore permissions for cleanup
                os.chmod(pages_dir, 0o755)

    @pytest.mark.asyncio
    async def test_handles_file_write_error_in_save_metadata(self):
        """CRITICAL 3: Test that file I/O errors in _save_metadata are caught"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            cycle.cycle_dir.mkdir(parents=True, exist_ok=True)

            # Make directory read-only to trigger write error
            os.chmod(cycle.cycle_dir, 0o444)

            try:
                subtopics = [{"name": "Test", "query": "test", "description": "test"}]
                pages = []

                # Should not crash with unhandled exception
                cycle._save_metadata(subtopics, pages)
            finally:
                # Restore permissions for cleanup
                os.chmod(cycle.cycle_dir, 0o755)

    @pytest.mark.asyncio
    async def test_handles_file_write_error_in_save_timing(self):
        """CRITICAL 3: Test that file I/O errors in _save_timing are caught"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            cycle.cycle_dir.mkdir(parents=True, exist_ok=True)

            # Make directory read-only to trigger write error
            os.chmod(cycle.cycle_dir, 0o444)

            try:
                from optimizer import TimingData

                timing = TimingData(
                    web_scan_seconds=1.0,
                    subtopic_detection_seconds=2.0,
                    page_collection_seconds=3.0,
                    quality_scoring_seconds=4.0,
                    total_seconds=10.0,
                )

                # Should not crash with unhandled exception
                cycle._save_timing(timing)
            finally:
                # Restore permissions for cleanup
                os.chmod(cycle.cycle_dir, 0o755)

    @pytest.mark.asyncio
    async def test_cycle_runs_all_phases(self):
        """Test that ResearchCycle executes all 5 phases"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)

            result = await cycle.run()

            assert result["cycle_num"] == 1
            assert "timing" in result
            assert "pages_collected" in result
            assert "quality_metrics" in result

            # Check timing has all phases
            timing = result["timing"]
            assert "web_scan_seconds" in timing
            assert "subtopic_detection_seconds" in timing
            assert "page_collection_seconds" in timing
            assert "quality_scoring_seconds" in timing
            assert "total_seconds" in timing

    @pytest.mark.asyncio
    async def test_cycle_collects_100_pages(self):
        """Test that cycle collects exactly 100 pages (20 per subtopic + cross-topic)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            result = await cycle.run()

            assert result["pages_collected"] == 100

    @pytest.mark.asyncio
    async def test_cycle_saves_to_output_structure(self):
        """Test that cycle saves results to proper directory structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            await cycle.run()

            # Check directory structure
            cycle_dir = Path(tmpdir) / "cycle-1"
            assert cycle_dir.exists()

            pages_dir = cycle_dir / "pages"
            assert pages_dir.exists()

            metadata_file = cycle_dir / "metadata.json"
            assert metadata_file.exists()

            timing_file = cycle_dir / "timing.csv"
            assert timing_file.exists()

    @pytest.mark.asyncio
    async def test_metadata_contains_quality_scores(self):
        """Test that metadata.json includes quality scores for all pages"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cycle = ResearchCycle(cycle_num=1, output_dir=tmpdir)
            await cycle.run()

            metadata_file = Path(tmpdir) / "cycle-1" / "metadata.json"
            with open(metadata_file) as f:
                metadata = json.load(f)

            assert "pages" in metadata
            assert len(metadata["pages"]) == 100

            # Each page should have quality metrics
            for page in metadata["pages"]:
                assert "url" in page
                assert "relevance_score" in page
                assert "credibility_score" in page
                assert "uniqueness_score" in page
                assert "overall_quality" in page
                assert 1 <= page["overall_quality"] <= 10


class TestOptimizationRunner:
    """RED Phase: Test the full optimization runner (5 cycles)"""

    @pytest.mark.asyncio
    async def test_handles_zero_quality_in_improvement_calculation(self):
        """CRITICAL 2: Test that division by zero is handled when first cycle quality is 0"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)

            # Manually create results with first cycle having 0 quality
            results = [
                {
                    "cycle_num": 1,
                    "pages_collected": 100,
                    "quality_metrics": {
                        "average_overall": 0,  # This would cause division by zero
                        "average_relevance": 0,
                        "average_credibility": 0,
                        "average_uniqueness": 0,
                    },
                    "timing": {"total_seconds": 10.0},
                    "subtopics": [],
                },
                {
                    "cycle_num": 2,
                    "pages_collected": 100,
                    "quality_metrics": {
                        "average_overall": 5.0,
                        "average_relevance": 5.0,
                        "average_credibility": 5.0,
                        "average_uniqueness": 5.0,
                    },
                    "timing": {"total_seconds": 8.0},
                    "subtopics": [],
                },
            ]

            # Should not crash with ZeroDivisionError
            runner._generate_optimization_report(results)

            report_file = Path(tmpdir) / "optimization_report.json"
            assert report_file.exists()

    @pytest.mark.asyncio
    async def test_handles_zero_timing_in_improvement_calculation(self):
        """CRITICAL 2: Test that division by zero is handled when first cycle timing is 0"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)

            # Manually create results with first cycle having 0 timing
            results = [
                {
                    "cycle_num": 1,
                    "pages_collected": 100,
                    "quality_metrics": {
                        "average_overall": 5.0,
                        "average_relevance": 5.0,
                        "average_credibility": 5.0,
                        "average_uniqueness": 5.0,
                    },
                    "timing": {"total_seconds": 0},  # This would cause division by zero
                    "subtopics": [],
                },
                {
                    "cycle_num": 2,
                    "pages_collected": 100,
                    "quality_metrics": {
                        "average_overall": 5.0,
                        "average_relevance": 5.0,
                        "average_credibility": 5.0,
                        "average_uniqueness": 5.0,
                    },
                    "timing": {"total_seconds": 8.0},
                    "subtopics": [],
                },
            ]

            # Should not crash with ZeroDivisionError
            runner._generate_optimization_report(results)

            report_file = Path(tmpdir) / "optimization_report.json"
            assert report_file.exists()

    @pytest.mark.asyncio
    async def test_runs_five_cycles(self):
        """Test that OptimizationRunner completes 5 cycles"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)
            results = await runner.run()

            assert len(results) == 5
            for i, result in enumerate(results):
                assert result["cycle_num"] == i + 1

    @pytest.mark.asyncio
    async def test_generates_optimization_report(self):
        """Test that runner generates final optimization report"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)
            await runner.run()

            report_file = Path(tmpdir) / "optimization_report.json"
            assert report_file.exists()

            with open(report_file) as f:
                report = json.load(f)

            assert "cycles" in report
            assert len(report["cycles"]) == 5
            assert "improvements" in report
            assert "recommendations" in report

    @pytest.mark.asyncio
    async def test_generates_recommendations_markdown(self):
        """Test that runner generates recommendations.md"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)
            await runner.run()

            recommendations_file = Path(tmpdir) / "recommendations.md"
            assert recommendations_file.exists()

            with open(recommendations_file) as f:
                content = f.read()

            assert "# OpenClaw Deep Research Optimization" in content
            assert "## Recommendations" in content
            assert "## Cycle Comparison" in content

    @pytest.mark.asyncio
    async def test_measures_timing_across_cycles(self):
        """Test that timing data is collected and compared across 5 cycles"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)
            results = await runner.run()

            report_file = Path(tmpdir) / "optimization_report.json"
            with open(report_file) as f:
                report = json.load(f)

            # Should show timing trends
            assert "timing_trends" in report
            timing_trends = report["timing_trends"]

            assert "average_seconds" in timing_trends
            assert "min_seconds" in timing_trends
            assert "max_seconds" in timing_trends

    @pytest.mark.asyncio
    async def test_measures_quality_improvements(self):
        """Test that quality improvements are tracked across cycles"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)
            results = await runner.run()

            report_file = Path(tmpdir) / "optimization_report.json"
            with open(report_file) as f:
                report = json.load(f)

            # Should show quality metrics progression
            assert "quality_trends" in report
            quality_trends = report["quality_trends"]

            assert "average_quality_scores" in quality_trends
            assert len(quality_trends["average_quality_scores"]) == 5


class TestCycleErrorHandling:
    """RED Phase: Test cycle-level exception handling"""

    @pytest.mark.asyncio
    async def test_runner_continues_if_cycle_fails(self):
        """CRITICAL 4: Test that runner continues running remaining cycles if one cycle fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)

            # Manually mock a cycle that will fail
            original_run = ResearchCycle.run

            async def failing_cycle_run(self):
                if self.cycle_num == 3:
                    raise Exception("Simulated cycle 3 failure")
                return await original_run(self)

            # Patch ResearchCycle.run
            ResearchCycle.run = failing_cycle_run

            try:
                # Runner should continue even if cycle 3 fails
                results = await runner.run()

                # Should have results from all cycles that succeeded
                assert len(results) >= 2  # At least cycles 1, 2, 4, 5 should complete
            finally:
                # Restore original method
                ResearchCycle.run = original_run

    @pytest.mark.asyncio
    async def test_runner_collects_partial_results_on_failure(self):
        """CRITICAL 4: Test that runner collects partial results even if some cycles fail"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = OptimizationRunner(output_dir=tmpdir)

            # Manually mock a cycle that will fail
            original_run = ResearchCycle.run

            async def failing_cycle_run(self):
                if self.cycle_num >= 4:
                    raise Exception("Simulated failure in later cycles")
                return await original_run(self)

            # Patch ResearchCycle.run
            ResearchCycle.run = failing_cycle_run

            try:
                # Runner should collect partial results
                results = await runner.run()

                # Should have results from cycles 1-3
                assert len(results) >= 3
            finally:
                # Restore original method
                ResearchCycle.run = original_run


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
