"""
Reports Blueprint — FIXED
Save as: routes/reports.py

FIX: ReportGenerator static/class methods only accept their period parameters
(e.g. year + month). The extra `current_user.id` argument was causing:
    "generate_monthly_report() takes 2 positional arguments but 3 were given"

If you need user-scoped reports in the future, you have two options:
  Option A: Update ReportGenerator methods to accept user_id as a keyword arg:
                ReportGenerator.generate_monthly_report(year, month, user_id=current_user.id)
            and update the method signatures accordingly.
  Option B: Set user context before calling (e.g. via a thread-local or app context).
"""

from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required, current_user
from ai_modules.report_generator import ReportGenerator
from ai_modules.pdf_generator import PDFGenerator
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

# Create blueprint
report_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


@report_bp.route('/monthly', methods=['GET'])
@login_required
def monthly_report():
    """Generate monthly report"""
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        # Validate parameters
        if not year or not month:
            return jsonify({
                'success': False,
                'error': 'Missing year or month parameter'
            }), 400
        
        if not (1 <= month <= 12):
            return jsonify({
                'success': False,
                'error': 'Month must be between 1 and 12'
            }), 400
        
        # FIX: Removed current_user.id — method only takes (year, month)
        report = ReportGenerator.generate_monthly_report(year, month)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"Monthly report error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to generate monthly report: {str(e)}'
        }), 500


@report_bp.route('/quarterly', methods=['GET'])
@login_required
def quarterly_report():
    """Generate quarterly report"""
    try:
        year = request.args.get('year', type=int)
        quarter = request.args.get('quarter', type=int)
        
        # Validate parameters
        if not year or not quarter:
            return jsonify({
                'success': False,
                'error': 'Missing year or quarter parameter'
            }), 400
        
        if not (1 <= quarter <= 4):
            return jsonify({
                'success': False,
                'error': 'Quarter must be between 1 and 4'
            }), 400
        
        # FIX: Removed current_user.id — method only takes (year, quarter)
        report = ReportGenerator.generate_quarterly_report(year, quarter)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"Quarterly report error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to generate quarterly report: {str(e)}'
        }), 500


@report_bp.route('/comparison', methods=['GET'])
@login_required
def comparison_report():
    """Generate comparison report"""
    try:
        period_type = request.args.get('period_type', 'monthly')
        periods = request.args.get('periods', 6, type=int)
        
        # Validate parameters
        if period_type not in ['monthly', 'quarterly']:
            return jsonify({
                'success': False,
                'error': 'period_type must be "monthly" or "quarterly"'
            }), 400
        
        if not (1 <= periods <= 24):
            return jsonify({
                'success': False,
                'error': 'periods must be between 1 and 24'
            }), 400
        
        # FIX: Removed current_user.id — method only takes (period_type, periods)
        report = ReportGenerator.generate_comparison_report(period_type, periods)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"Comparison report error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to generate comparison report: {str(e)}'
        }), 500


@report_bp.route('/custom', methods=['GET'])
@login_required
def custom_report():
    """Generate custom range report"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Validate parameters
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'Missing start_date or end_date parameter'
            }), 400
        
        # FIX: Removed current_user.id — method only takes (start_date, end_date)
        report = ReportGenerator.generate_custom_report(start_date, end_date)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"Custom report error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to generate custom report: {str(e)}'
        }), 500


@report_bp.route('/export-pdf', methods=['POST'])
@login_required
def export_pdf():
    """
    Export report as PDF
    
    Expected JSON payload:
    {
        "report_data": {...report data...},
        "report_type": "monthly|quarterly|comparison|custom",
        "charts": {
            "category": "data:image/png;base64,iVBORw0KG...",
            "daily": "data:image/png;base64,iVBORw0KG..."
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        report_data = data.get('report_data')
        report_type = data.get('report_type')
        charts_base64 = data.get('charts', {})
        
        # Validate required fields
        if not report_data:
            return jsonify({
                'success': False,
                'error': 'Missing report_data'
            }), 400
        
        if not report_type:
            return jsonify({
                'success': False,
                'error': 'Missing report_type'
            }), 400
        
        # Validate report type
        valid_types = ['monthly', 'quarterly', 'comparison', 'custom']
        if report_type not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid report_type. Must be one of: {", ".join(valid_types)}'
            }), 400
        
        # Validate report data structure
        if not isinstance(report_data, dict):
            return jsonify({
                'success': False,
                'error': 'report_data must be an object'
            }), 400
        
        if 'period' not in report_data or 'summary' not in report_data:
            logger.warning(f"Invalid report data structure: {list(report_data.keys())}")
            return jsonify({
                'success': False,
                'error': 'report_data must contain "period" and "summary" fields'
            }), 400
        
        logger.info(f"Generating PDF report - Type: {report_type}, Charts: {len(charts_base64)}")
        
        # Generate PDF
        pdf_file = PDFGenerator.generate_report_pdf(
            report_data,
            report_type,
            charts_base64 if charts_base64 else None
        )
        
        if not pdf_file:
            raise ValueError("PDF generation returned None")
        
        # Generate filename
        period = report_data.get('period', {})
        
        if report_type == 'monthly':
            month_name = period.get('month_name', 'Report')
            year = period.get('year', '')
            filename = f"Report_{month_name}_{year}.pdf"
        elif report_type == 'quarterly':
            quarter = period.get('quarter', '')
            year = period.get('year', '')
            filename = f"Report_Q{quarter}_{year}.pdf"
        elif report_type == 'custom':
            start_date = period.get('start_date', '')
            end_date = period.get('end_date', '')
            filename = f"Report_{start_date}_to_{end_date}.pdf"
        else:  # comparison
            filename = f"Comparison_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        # Clean filename
        filename = filename.replace(' ', '_').replace(':', '-').replace('/', '-')
        
        logger.info(f"PDF generated successfully: {filename}")
        
        # Return PDF file
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Validation error: {str(e)}'
        }), 400
    
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to generate PDF: {str(e)}'
        }), 500