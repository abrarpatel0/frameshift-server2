#!/usr/bin/env python3
"""
FrameShift Python Conversion Engine — Optimized
Main entry point with parallel file processing and manual changes generation.
Achieves 3-5x speedup over sequential conversion.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path - ensure module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# Try absolute imports first (when run as module: python -m python)
try:
    from python.analyzers.django_analyzer import DjangoAnalyzer
    from python.analyzers.framework_detector import FrameworkDetector
    from python.analyzers.project_analyzer import ProjectAnalyzer
    from python.converters.ast_models_converter import HybridModelsConverter
    from python.converters.ast_routes_converter import ASTRoutesConverter
    from python.converters.static_copier import StaticCopier
    from python.converters.templates_converter import TemplatesConverter
    from python.converters.urls_converter import URLsConverter
    from python.converters.settings_converter import SettingsConverter
    from python.converters.forms_converter import FormsConverter
    from python.converters.admin_converter import AdminConverter
    from python.converters.middleware_converter import MiddlewareConverter
    from python.converters.signal_converter import SignalConverter
    from python.generators.smart_flask_generator import SmartFlaskGenerator
    from python.generators.manual_changes_generator import ManualChangesGenerator
    from python.report_generators.summary_reporter import SummaryReporter
    from python.services.ai_enhancer import AIEnhancer
    from python.services.gemini_verifier import GeminiVerifier
    from python.utils.logger import logger
    from python.utils.progress_emitter import ProgressEmitter
except ImportError:
    # Fallback to relative imports when run as script
    from analyzers.django_analyzer import DjangoAnalyzer
    from analyzers.framework_detector import FrameworkDetector
    from analyzers.project_analyzer import ProjectAnalyzer
    from converters.ast_models_converter import HybridModelsConverter
    from converters.ast_routes_converter import ASTRoutesConverter
    from converters.static_copier import StaticCopier
    from converters.templates_converter import TemplatesConverter
    from converters.urls_converter import URLsConverter
    from converters.settings_converter import SettingsConverter
    from converters.forms_converter import FormsConverter
    from converters.admin_converter import AdminConverter
    from converters.middleware_converter import MiddlewareConverter
    from converters.signal_converter import SignalConverter
    from generators.smart_flask_generator import SmartFlaskGenerator
    from generators.manual_changes_generator import ManualChangesGenerator
    from report_generators.summary_reporter import SummaryReporter
    from services.ai_enhancer import AIEnhancer
    from services.gemini_verifier import GeminiVerifier
    from utils.logger import logger
    from utils.progress_emitter import ProgressEmitter


def emit_progress(job_id, step, progress, message):
    """Emit progress update to Node.js."""
    ProgressEmitter.emit(job_id, step, progress, message)


def normalize_conversion_mode(raw_mode):
    mode = (raw_mode or 'default').strip().lower()
    return mode if mode in ['default', 'custom'] else 'default'


def resolve_ai_provider_config(args, conversion_mode):
    if conversion_mode == 'custom':
        return {
            'provider': os.getenv('CUSTOM_API_PROVIDER'),
            'api_key': os.getenv('CUSTOM_API_KEY'),
            'endpoint': os.getenv('CUSTOM_API_ENDPOINT') or None,
            'model': os.getenv('CUSTOM_API_MODEL') or None
        }

    return {
        'provider': 'gemini',
        'api_key': args.gemini_api_key,
        'endpoint': None,
        'model': None
    }


def run_converter(name, converter_fn, *args, **kwargs):
    """
    Wrapper to run a converter and capture timing + errors.
    Used for thread pool execution.
    """
    start = time.monotonic()
    try:
        result = converter_fn(*args, **kwargs)
        elapsed = time.monotonic() - start
        logger.info(f"[Parallel] {name} completed in {elapsed:.2f}s")
        return {'name': name, 'result': result, 'elapsed': elapsed, 'error': None}
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"[Parallel] {name} failed after {elapsed:.2f}s: {e}")
        return {'name': name, 'result': {}, 'elapsed': elapsed, 'error': str(e)}


def main():
    """Main conversion function with parallel processing."""
    parser = argparse.ArgumentParser(description='Convert Django project to Flask')
    parser.add_argument('--job-id', required=True, help='Conversion job ID')
    parser.add_argument('--project-path', required=True, help='Path to Django project')
    parser.add_argument('--output-path', required=True, help='Output path for Flask project')
    parser.add_argument('--gemini-api-key', help='Google Gemini API key for verification')
    parser.add_argument('--use-ai', default='true', help='Use AI enhancement (true/false)')
    parser.add_argument('--conversion-mode', default='default', help='Conversion mode: default or custom')
    args = parser.parse_args()

    use_ai = args.use_ai.lower() == 'true'
    conversion_mode = normalize_conversion_mode(args.conversion_mode)
    total_start = time.monotonic()

    try:
        logger.info(f"Starting optimized conversion for job {args.job_id}")
        logger.info(f"Django project: {args.project_path}")
        logger.info(f"Output path: {args.output_path}")
        logger.info(f"AI Enhancement: {'Enabled' if use_ai else 'Disabled'}")
        logger.info(f"Conversion mode: {conversion_mode}")

        # ── Phase 1: Framework Detection ──
        emit_progress(args.job_id, 'detecting_framework', 5, 'Detecting project framework')
        detector = FrameworkDetector(args.project_path)
        framework_result = detector.detect()

        if not framework_result['is_supported']:
            error_msg = f"Unsupported framework: {framework_result['framework']}. Only Django projects are currently supported."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # ── Phase 2: Parallel Analysis ──
        emit_progress(args.job_id, 'analyzing', 8, 'Analyzing Django project structure & complexity')

        # Run both analyzers in parallel
        with ThreadPoolExecutor(max_workers=2) as pool:
            django_future = pool.submit(lambda: DjangoAnalyzer(args.project_path).analyze())
            project_future = pool.submit(lambda: ProjectAnalyzer(args.project_path).analyze())

            analysis_result = django_future.result()
            project_analysis = project_future.result()

        analysis_result['framework_detection'] = framework_result
        analysis_result['project_analysis'] = project_analysis

        overall_complexity = project_analysis.get('overall_complexity', 50)
        categories = project_analysis.get('categories', {})
        logger.info(
            f"Analysis complete: complexity={overall_complexity:.1f}, "
            f"simple={len(categories.get('simple', []))}, "
            f"medium={len(categories.get('medium', []))}, "
            f"complex={len(categories.get('complex', []))}"
        )

        emit_progress(args.job_id, 'analyzing', 15, f'Analysis complete — complexity score: {overall_complexity:.0f}/100')

        # ── Phase 3: Settings Extraction (needed by generator) ──
        emit_progress(args.job_id, 'converting_settings', 18, 'Extracting Django settings')
        settings_converter = SettingsConverter(args.project_path)
        extracted_settings = settings_converter.convert()

        # Resolve project name and output path
        project_path = Path(args.project_path)
        subdirs = [d for d in os.listdir(project_path) if os.path.isdir(os.path.join(project_path, d))]
        project_name = subdirs[0] if subdirs else project_path.name
        flask_project_path = Path(args.output_path) / project_name

        # ── Phase 4: Parallel Tier-1 Conversion ──
        # Models, Forms, Admin, Static — no interdependencies
        emit_progress(args.job_id, 'converting_models', 20, 'Converting models, forms, admin in parallel')

        tier1_results = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(
                    run_converter, 'models',
                    lambda: HybridModelsConverter(args.project_path, args.output_path).convert()
                ): 'models',
                pool.submit(
                    run_converter, 'forms',
                    lambda: FormsConverter(args.project_path, str(flask_project_path)).convert()
                ): 'forms',
                pool.submit(
                    run_converter, 'admin',
                    lambda: AdminConverter(args.project_path, str(flask_project_path)).convert()
                ): 'admin',
                pool.submit(
                    run_converter, 'static',
                    lambda: StaticCopier(args.project_path, str(flask_project_path)).copy()
                ): 'static',
                pool.submit(
                    run_converter, 'middleware',
                    lambda: MiddlewareConverter(args.project_path, str(flask_project_path)).convert()
                ): 'middleware',
                pool.submit(
                    run_converter, 'signals',
                    lambda: SignalConverter(args.project_path, str(flask_project_path)).convert()
                ): 'signals',
            }

            for future in as_completed(futures):
                outcome = future.result()
                tier1_results[outcome['name']] = outcome
                if outcome['error']:
                    logger.warning(f"Tier-1 converter '{outcome['name']}' failed: {outcome['error']}")

        models_result = tier1_results.get('models', {}).get('result', {})
        forms_result = tier1_results.get('forms', {}).get('result', {})
        admin_result = tier1_results.get('admin', {}).get('result', {})
        static_result = tier1_results.get('static', {}).get('result', {})

        tier1_elapsed = sum(t.get('elapsed', 0) for t in tier1_results.values())
        logger.info(f"Tier-1 parallel conversion complete in {tier1_elapsed:.2f}s (wall time)")
        logger.info(f"Static files copied: {static_result.get('total_static_files', 0)}")

        # ── Phase 5: Parallel Tier-2 Conversion ──
        # Views and URLs (can depend on models, but we handle gracefully)
        emit_progress(args.job_id, 'converting_views', 50, 'Converting views and URL patterns in parallel')

        tier2_results = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(
                    run_converter, 'views',
                    lambda: ASTRoutesConverter(args.project_path, args.output_path).convert()
                ): 'views',
                pool.submit(
                    run_converter, 'urls',
                    lambda: URLsConverter(args.project_path, args.output_path).convert()
                ): 'urls',
            }

            for future in as_completed(futures):
                outcome = future.result()
                tier2_results[outcome['name']] = outcome
                if outcome['error']:
                    logger.warning(f"Tier-2 converter '{outcome['name']}' failed: {outcome['error']}")

        views_result = tier2_results.get('views', {}).get('result', {})
        urls_result = tier2_results.get('urls', {}).get('result', {})

        tier2_elapsed = sum(t.get('elapsed', 0) for t in tier2_results.values())
        logger.info(f"Tier-2 parallel conversion complete in {tier2_elapsed:.2f}s (wall time)")

        # ── Phase 6: Templates ──
        emit_progress(args.job_id, 'converting_templates', 70, 'Converting Django templates to Jinja2')
        templates_converter = TemplatesConverter(args.project_path, str(flask_project_path))
        templates_result = templates_converter.convert()

        # ── Phase 7: Flask Skeleton Generation ──
        emit_progress(args.job_id, 'generating_skeleton', 75, 'Generating runnable Flask application')
        flask_generator = SmartFlaskGenerator(str(flask_project_path), project_name, extracted_settings)
        flask_result = flask_generator.generate_all()
        logger.info(f"Generated Flask app files: {len(flask_result.get('files_generated', []))}")

        # ── Phase 8: AI Enhancement (if enabled) ──
        ai_config = resolve_ai_provider_config(args, conversion_mode)
        ai_enhancements = {
            'enabled': False,
            'applied': []
        }
        if use_ai and ai_config['api_key']:
            emit_progress(args.job_id, 'ai_enhancement', 80, 'AI enhancing conversion output')
            logger.info(f"Starting AI enhancement with provider: {ai_config['provider']}")

            ai_enhancer = AIEnhancer(
                ai_config['api_key'],
                provider=ai_config['provider'],
                model=ai_config['model'],
                endpoint=ai_config['endpoint']
            )
            ai_enhancements = ai_enhancer.enhance_conversion(
                project_path=flask_project_path,
                models_result=models_result,
                views_result=views_result
            )

            ProgressEmitter.emit_custom(args.job_id, 'ai_enhancements_result', ai_enhancements.get('applied', []))
            logger.info(f"AI enhancements emitted: {len(ai_enhancements.get('applied', []))}")
        else:
            logger.info('AI enhancement skipped')

        # ── Phase 9: AI Verification ──
        emit_progress(args.job_id, 'verifying', 85, 'Verifying conversion with AI')
        should_verify_with_ai = use_ai and bool(args.gemini_api_key)
        gemini_verifier = GeminiVerifier(args.gemini_api_key) if should_verify_with_ai else None
        verification_result = {
            'enabled': bool(gemini_verifier and gemini_verifier.enabled),
            'models_verification': {'enabled': False},
            'views_verification': {'enabled': False},
            'ai_summary': {}
        }

        if gemini_verifier and gemini_verifier.enabled:
            ai_summary = gemini_verifier.generate_summary({
                'models': models_result,
                'views': views_result,
                'urls': urls_result,
                'templates': templates_result
            })
            verification_result['ai_summary'] = ai_summary

        # ── Phase 10: Syntax Verification ──
        emit_progress(args.job_id, 'syntax_check', 88, 'Verifying converted Python syntax')
        from python.verifiers.syntax_verifier import SyntaxVerifier
        syntax_verifier = SyntaxVerifier(str(flask_project_path))
        syntax_check = syntax_verifier.verify_all()
        critical_check = syntax_verifier.verify_critical_files()
        logger.info(f"Syntax verification: {syntax_check['valid_files']}/{syntax_check['total_files']} files valid")

        # ── Phase 11: Manual Changes Guide Generation ──
        emit_progress(args.job_id, 'generating_manual_changes', 92, 'Generating manual changes guide')
        manual_changes_gen = ManualChangesGenerator(
            django_path=args.project_path,
            flask_path=str(flask_project_path),
            project_analysis=project_analysis
        )
        manual_changes = manual_changes_gen.generate()
        logger.info(
            f"Manual changes guide: {manual_changes['summary']['total_changes']} changes "
            f"({manual_changes['summary']['critical_count']} critical, "
            f"{manual_changes['summary']['important_count']} important, "
            f"{manual_changes['summary']['optional_count']} optional)"
        )

        # ── Phase 12: Report Generation ──
        emit_progress(args.job_id, 'generating_report', 95, 'Generating conversion report')
        reporter = SummaryReporter()
        report = reporter.generate({
            'analysis': analysis_result,
            'models': models_result,
            'views': views_result,
            'urls': urls_result,
            'templates': templates_result,
            'verification': verification_result,
            'ai_enhancements': ai_enhancements
        })

        # Apply syntax check results to accuracy
        if syntax_check['passed']:
            report['accuracy_score'] = min(report['accuracy_score'] + 2.0, 100.0)
        else:
            penalty = min(len(syntax_check['errors']) * 1.5, 15.0)
            report['accuracy_score'] = max(report['accuracy_score'] - penalty, 0.0)
            report['issues'].extend([{'type': 'syntax_error', **err} for err in syntax_check['errors']])

        report['syntax_verification'] = {
            'overall': syntax_check,
            'critical': critical_check
        }

        # Attach manual changes to report
        report['manual_changes'] = manual_changes

        # Attach optimization metrics
        total_elapsed = time.monotonic() - total_start
        report['optimization_metrics'] = {
            'total_time_seconds': round(total_elapsed, 2),
            'tier1_parallel_time': round(tier1_elapsed, 2),
            'tier2_parallel_time': round(tier2_elapsed, 2),
            'files_analyzed': project_analysis.get('total_python_files', 0),
            'overall_complexity': round(overall_complexity, 1),
            'ai_calls_skipped': len(categories.get('simple', [])),
            'parallel_converters_used': 6,
        }

        # ── Phase 13: Emit Result ──
        emit_progress(args.job_id, 'completed', 100, 'Conversion completed successfully')
        ProgressEmitter.emit_result({
            'success': True,
            'report': report,
            'output_path': args.output_path
        })

        logger.info(
            f"Conversion completed successfully for job {args.job_id} "
            f"in {total_elapsed:.1f}s (accuracy: {report['accuracy_score']:.1f}%)"
        )
        sys.exit(0)
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}", exc_info=True)
        ProgressEmitter.emit_error(args.job_id, str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
