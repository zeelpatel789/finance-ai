from flask import Flask, render_template, jsonify, request
from config import Config
from models.database import db, init_db
from models.document import Document
from models.transaction import Transaction
from models.category import Category, DEFAULT_CATEGORIES
from models.budget import Budget
from utils.db_utils import DatabaseUtils
from utils.seed_data import SeedData
from flask import request, redirect, url_for
from utils.file_handler import FileHandler
from werkzeug.utils import secure_filename
from utils.processor import DocumentProcessingWorkflow
from ai_modules.smart_nlp import EnhancedSmartNLPProcessor
from utils.performance_monitor import perf_monitor
from models.conversation import Conversation
from models.message import Message
from routes.chat_routes_semantic import chat_bp
from routes.reports import report_bp
import os
from routes.budget_routes import budget_bp
from routes.insights_routes import insights_bp 
from datetime import datetime
from models.notification_system import Notification, NotificationManager, BudgetNotificationManager
from routes.notification_routes import notification_bp
from routes.hdfc_routes import hdfc_bp
from flask import jsonify, request
from sqlalchemy import func, desc
from models.user import User  # NEW
from flask_login import LoginManager, login_required, current_user  # NEW
from routes.auth_routes import auth_bp  # NEW


def create_app():
    """Application factory with authentication"""

    import os
    from flask import Flask
    from flask_login import LoginManager
    from config import Config
    from models.database import init_db, db
    from models.user import User
    from models.category import Category, DEFAULT_CATEGORIES

    # 🔥 FIX: Force correct static path (Render + Gunicorn safe)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, "static"),
        static_url_path="/static"
    )

    app.config.from_object(Config)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    init_db(app)

    
    # ========================================================================
    # FLASK-LOGIN SETUP
    # ========================================================================
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Redirect to login page if not authenticated
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        return db.session.get(User, int(user_id))
    
    # ========================================================================
    # DATABASE INITIALIZATION
    # ========================================================================
    
    # Seed default categories
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created/verified")
        
        # Seed default categories if empty
        if Category.query.count() == 0:
            for cat_data in DEFAULT_CATEGORIES:
                category = Category(**cat_data)
                db.session.add(category)
            db.session.commit()
            print("✅ Default categories created!")
    
    return app

app = create_app()

# Register blueprints
app.register_blueprint(auth_bp)  # NEW - Must be registered FIRST
app.register_blueprint(chat_bp)
app.register_blueprint(report_bp)
app.register_blueprint(budget_bp)
app.register_blueprint(insights_bp) 
app.register_blueprint(notification_bp)
app.register_blueprint(hdfc_bp)



# ============= ROUTES =============

@app.route('/')
@login_required  # NEW - Protect dashboard
def index():
    """Dashboard home page"""
    return render_template('index.html')

@app.route('/health')
@login_required
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'version': '1.0.0'
    })

@app.route('/api/stats')
@login_required
def get_stats():
    """Get dashboard statistics"""
    stats = DatabaseUtils.get_dashboard_stats()
    return jsonify(stats)

@app.route('/api/category-breakdown')
@login_required
def get_category_breakdown():
    """Get category-wise breakdown"""
    breakdown = DatabaseUtils.get_category_breakdown()
    return jsonify(breakdown)

@app.route('/api/recent-transactions')
@login_required
def get_recent_transactions():
    """Get recent transactions"""
    limit = request.args.get('limit', 10, type=int)
    transactions = DatabaseUtils.get_recent_transactions(limit)
    return jsonify(transactions)

@app.route('/api/monthly-trend')
@login_required
def get_monthly_trend():
    """Get monthly spending trend"""
    months = request.args.get('months', 6, type=int)
    trend = DatabaseUtils.get_monthly_trend(months)
    return jsonify(trend)



# Replace the existing /api/vendors/top route in your app.py with this:

@app.route('/api/vendors/top')
@login_required
def get_top_vendors():
    """Get top vendors by spending"""
    try:
        limit = request.args.get('limit', 6, type=int)
        
        # Query top vendors grouped by vendor_name (not vendor!)
        vendors = db.session.query(
            Transaction.vendor_name.label('vendor_name'),
            func.count(Transaction.id).label('transaction_count'),
            func.sum(Transaction.amount).label('total_spending'),
            func.max(Transaction.transaction_date).label('last_transaction_date')
        ).filter(
            Transaction.vendor_name.isnot(None),  # Exclude NULL vendors
            Transaction.vendor_name != ''  # Exclude empty vendors
        ).group_by(
            Transaction.vendor_name
        ).order_by(
            desc('total_spending')
        ).limit(limit).all()
        
        # Format results
        vendor_list = []
        for v in vendors:
            try:
                # Handle date safely
                last_date = None
                if v.last_transaction_date:
                    if isinstance(v.last_transaction_date, str):
                        last_date = v.last_transaction_date
                    else:
                        last_date = v.last_transaction_date.isoformat()
                
                vendor_list.append({
                    'vendor_name': str(v.vendor_name) if v.vendor_name else 'Unknown',
                    'transaction_count': int(v.transaction_count) if v.transaction_count else 0,
                    'total_spending': float(v.total_spending) if v.total_spending else 0.0,
                    'last_transaction_date': last_date
                })
            except Exception as e:
                print(f"Error processing vendor {v}: {str(e)}")
                continue
        
        print(f"✅ Found {len(vendor_list)} vendors")
        
        return jsonify({
            'success': True,
            'vendors': vendor_list
        })
        
    except Exception as e:
        # Detailed error logging
        print(f"❌ Error in get_top_vendors: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Check server logs for details'
        }), 500
        
@app.route('/api/categories')
@login_required
def get_categories():
    """Get all categories"""
    categories = Category.query.all()
    return jsonify([cat.to_dict() for cat in categories])

# ============= ADMIN/DEBUG ROUTES =============

# Replace the /admin/seed route with this improved version:

@app.route('/admin/seed')
@login_required
def seed_database():
    """Seed database with dummy data"""
    try:
        SeedData.generate_documents(10)
        SeedData.generate_transactions(50)
        
        # Get counts
        doc_count = Document.query.count()
        trans_count = Transaction.query.count()
        
        return jsonify({
            'success': True,
            'message': 'Database seeded successfully!',
            'documents': doc_count,
            'transactions': trans_count
        })
    except Exception as e:
        # Print full error to console
        import traceback
        print("❌ SEEDING ERROR:")
        print(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/clear')
@login_required
def clear_database():
    """Clear all data (WARNING: Use with caution!)"""
    try:
        SeedData.clear_all_data()
        return jsonify({
            'success': True,
            'message': 'All data cleared successfully!'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Add this route
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_page():
    """Upload page and file upload handler"""
    if request.method == 'GET':
        return render_template('upload.html')
    
    # POST - Handle file upload
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Save file
    file_info, error = FileHandler.save_file(file, app.config['UPLOAD_FOLDER'])
    
    if error:
        return jsonify({'success': False, 'error': error}), 400
    
    try:
        # Determine file type
        file_type = FileHandler.get_file_type(file_info['original_filename'])
        
        # Save to database
        document = Document(
            filename=file_info['saved_filename'],
            original_filename=file_info['original_filename'],
            file_type=file_type,
            file_path=file_info['file_path'],
            processed=False
        )
        
        db.session.add(document)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'document': document.to_dict()
        })
        
    except Exception as e:
        # If database save fails, delete the uploaded file
        FileHandler.delete_file(file_info['file_path'])
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents')
@login_required
def get_documents():
    """Get all uploaded documents"""
    documents = Document.query.order_by(Document.upload_date.desc()).all()
    return jsonify([doc.to_dict() for doc in documents])

@app.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_document(doc_id):
    """Delete a document"""
    try:
        document = db.session.get(Document, doc_id)
        
        if not document:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        # Delete file from disk
        FileHandler.delete_file(document.file_path)
        
        # Delete from database
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Document deleted successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/documents/<int:doc_id>')
@login_required
def get_document(doc_id):
    """Get a single document"""
    document = db.session.get(Document, doc_id)
    if not document:
        return jsonify({'error': 'Document not found'}), 404
    return jsonify(document.to_dict())

@app.route('/uploads/<filename>')
@login_required
def serve_upload(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialize processor
processor = DocumentProcessingWorkflow()

@app.route('/api/process-document/<int:doc_id>', methods=['POST'])
@login_required
def process_document(doc_id):
    """Process a single document"""
    try:
        success, message = processor.process_document(doc_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/process-all-documents', methods=['POST'])
@login_required
def process_all_documents():
    """Process all unprocessed documents"""
    try:
        documents = Document.query.filter_by(processed=False).all()
        
        if not documents:
            return jsonify({
                'success': True,
                'message': 'No documents to process',
                'processed_count': 0
            })
        
        success_count = 0
        failed_count = 0
        errors = []
        
        for doc in documents:
            success, message = processor.process_document(doc.id)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"{doc.original_filename}: {message}")
        
        return jsonify({
            'success': True,
            'message': f'Processed {success_count} documents',
            'processed_count': success_count,
            'failed_count': failed_count,
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/document-details/<int:doc_id>')
@login_required
def get_document_details(doc_id):
    """Get detailed document information including extracted data"""
    try:
        document = db.session.get(Document, doc_id)
        
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        # Get associated transactions
        transactions = Transaction.query.filter_by(document_id=doc_id).all()
        
        return jsonify({
            'document': document.to_dict(),
            'raw_text': document.raw_text[:500] if document.raw_text else None,
            'transactions': [t.to_dict() for t in transactions],
            'transaction_count': len(transactions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# Initialize NLP processor
nlp_processor = None

@app.route('/chat')
@login_required
def chat_page():
    """Chat interface page"""
    return render_template('chat.html')

@app.route('/api/query', methods=['POST'])
@login_required
def process_query():
    """Process natural language query with advanced AI"""
    try:
        global nlp_processor
        
        # Initialize Smart NLP processor on first use
        if nlp_processor is None:
            print("🔄 Initializing NLP Processor...")
            nlp_processor = EnhancedSmartNLPProcessor()
            print("✅ Smart NLP Processor initialized")
        
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'No query provided'
            }), 400
        
        print(f"\n{'='*60}")
        print(f"📝 Processing query: {query}")
        print(f"{'='*60}")
        
        # Process query with smart NLP
        result = nlp_processor.process_query_smart(query)
        
        print(f"✅ Query processed successfully")
        print(f"   Intent: {result.get('intent', 'unknown')}")
        print(f"   Confidence: {result.get('confidence', 0):.1f}%")
        print(f"   Time: {result.get('processing_time', 'N/A')}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        # DETAILED ERROR LOGGING
        print(f"\n{'='*60}")
        print(f"❌ QUERY PROCESSING ERROR")
        print(f"{'='*60}")
        print(f"Query: {data.get('query', 'N/A') if 'data' in locals() else 'N/A'}")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"\nFull Traceback:")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': False,
            'error': f"{type(e).__name__}: {str(e)}"
        }), 500
    
# Add endpoint to clear conversation context
@app.route('/api/clear-context', methods=['POST'])
@login_required
def clear_context():
    """Clear conversation context"""
    try:
        global nlp_processor
        if nlp_processor:
            nlp_processor.clear_context()
        return jsonify({
            'success': True,
            'message': 'Context cleared'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/api/performance-stats')
@login_required
def get_performance_stats():
    """Get NLP performance statistics"""
    stats = perf_monitor.get_stats()
    return jsonify(stats)

@app.route('/reports')
@login_required
def reports_page():
    """Reports page"""
    return render_template('reports.html')
        
@app.route('/budgets')
@login_required
def budgets_page():
    """Budget tracking page"""
    return render_template('budgets.html')

@app.route('/insights')
@login_required
def insights_page():
    """Advanced insights page"""
    return render_template('insights.html')

@app.route('/notifications')
@login_required
def notifications_page():
    """Notification center page"""
    return render_template('notification_center.html')

# ============================================================================
# TRANSACTIONS PAGE & API ENDPOINTS
# ============================================================================

@app.route('/api/transactions', methods=['POST'])
@login_required
def create_transaction():
    """Create a manual transaction (with auto budget sync)"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'vendor_name', 'category_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid amount: {str(e)}'
            }), 400
        
        # Parse date
        transaction_date = None
        if data.get('transaction_date'):
            try:
                transaction_date = datetime.strptime(
                    data['transaction_date'], 
                    '%Y-%m-%d'
                ).date()
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }), 400
        
        # Validate category exists
        category = Category.query.get(data['category_id'])
        if not category:
            return jsonify({
                'success': False,
                'error': 'Invalid category ID'
            }), 400
        
        # Create transaction
        transaction = Transaction(
            document_id=None,
            transaction_date=transaction_date or datetime.now().date(),
            amount=amount,
            currency=data.get('currency', 'INR'),
            vendor_name=data['vendor_name'].strip(),
            description=data.get('description', 'Manual entry').strip(),
            category_id=data['category_id'],
            payment_method=data.get('payment_method', 'Other'),
            tax_amount=float(data.get('tax_amount', 0.0)),
            tax_percentage=float(data.get('tax_percentage', 0.0)) if data.get('tax_percentage') else None
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # ✅ AUTO-SYNC BUDGET
        from utils.budget_utils import BudgetUtils
        BudgetUtils.sync_transaction_budgets(transaction)
        
        print(f"✅ Transaction created: {transaction.vendor_name} - ₹{transaction.amount}")
        
        return jsonify({
            'success': True,
            'message': 'Transaction created successfully',
            'transaction': transaction.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transactions/<int:trans_id>', methods=['PUT'])
@login_required
def update_transaction(trans_id):
    """Update an existing transaction (with auto budget sync)"""
    
    transaction = Transaction.query.get(trans_id)
    
    if not transaction:
        return jsonify({
            'success': False,
            'error': 'Transaction not found'
        }), 404
    
    try:
        data = request.get_json()
        
        # ✅ STORE OLD VALUES FOR BUDGET SYNC
        old_category_id = transaction.category_id
        old_date = transaction.transaction_date
        
        # Update fields if provided
        if 'amount' in data:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({
                    'success': False,
                    'error': 'Amount must be positive'
                }), 400
            transaction.amount = amount
        
        if 'vendor_name' in data:
            transaction.vendor_name = data['vendor_name'].strip()
        
        if 'transaction_date' in data:
            transaction.transaction_date = datetime.strptime(
                data['transaction_date'], '%Y-%m-%d'
            ).date()
        
        if 'category_id' in data:
            # Validate category
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({
                    'success': False,
                    'error': 'Invalid category ID'
                }), 400
            transaction.category_id = data['category_id']
        
        if 'description' in data:
            transaction.description = data['description'].strip()
        
        if 'payment_method' in data:
            transaction.payment_method = data['payment_method']
        
        if 'tax_amount' in data:
            transaction.tax_amount = float(data['tax_amount'])
        
        # Update timestamp
        transaction.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # ✅ AUTO-SYNC AFFECTED BUDGETS
        from utils.budget_utils import BudgetUtils
        BudgetUtils.sync_transaction_budgets(
            transaction,
            old_category_id=old_category_id,
            old_date=old_date
        )
        
        print(f"✅ Transaction updated: {transaction.id}")
        
        return jsonify({
            'success': True,
            'message': 'Transaction updated successfully',
            'transaction': transaction.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating transaction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# STEP 4: Update app.py - Add to transaction delete route
# Replace your existing delete_transaction() function
# ============================================================================

@app.route('/api/transactions/<int:trans_id>', methods=['DELETE'])
@login_required
def delete_transaction(trans_id):
    """Delete a transaction (with auto budget sync)"""
    
    transaction = Transaction.query.get(trans_id)
    
    if not transaction:
        return jsonify({
            'success': False,
            'error': 'Transaction not found'
        }), 404
    
    try:
        # ✅ STORE VALUES BEFORE DELETION
        category_id = transaction.category_id
        transaction_date = transaction.transaction_date
        
        db.session.delete(transaction)
        db.session.commit()
        
        # ✅ AUTO-SYNC BUDGET
        from utils.budget_utils import BudgetUtils
        BudgetUtils.sync_deleted_transaction_budget(category_id, transaction_date)
        
        print(f"✅ Transaction deleted: {trans_id}")
        
        return jsonify({
            'success': True,
            'message': 'Transaction deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting transaction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@app.route('/transactions')
@login_required
def transactions_page():
    """Transactions management page"""
    return render_template('transactions.html')

@app.route('/hdfc-sync')
@login_required
def hdfc_sync_page():
    return render_template('hdfc_sync.html')


@app.route('/api/transactions', methods=['GET', 'POST'])
@login_required
def handle_transactions():
    """Get all transactions or create a new one"""
    
    if request.method == 'GET':
        # GET - Retrieve transactions with filters
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            category_id = request.args.get('category_id', type=int)
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            payment_method = request.args.get('payment_method')
            
            # Build query
            query = Transaction.query
            
            # Apply filters
            if category_id:
                query = query.filter_by(category_id=category_id)
            
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Transaction.transaction_date >= start)
            
            if end_date:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Transaction.transaction_date <= end)
            
            if payment_method:
                query = query.filter_by(payment_method=payment_method)
            
            # Order by date (most recent first)
            query = query.order_by(Transaction.transaction_date.desc())
            
            # Paginate
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)
            
            return jsonify({
                'success': True,
                'transactions': [t.to_dict() for t in paginated.items],
                'total': paginated.total,
                'page': page,
                'pages': paginated.pages,
                'per_page': per_page
            })
            
        except Exception as e:
            print(f"❌ Error fetching transactions: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        # POST - Create new transaction
        try:
            data = request.get_json()
            
            # Validate required fields
            required_fields = ['amount', 'vendor_name', 'category_id']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }), 400
            
            # Validate amount
            try:
                amount = float(data['amount'])
                if amount <= 0:
                    raise ValueError("Amount must be positive")
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid amount: {str(e)}'
                }), 400
            
            # Parse date
            transaction_date = None
            if data.get('transaction_date'):
                try:
                    transaction_date = datetime.strptime(
                        data['transaction_date'], 
                        '%Y-%m-%d'
                    ).date()
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid date format. Use YYYY-MM-DD'
                    }), 400
            
            # Validate category exists
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({
                    'success': False,
                    'error': 'Invalid category ID'
                }), 400
            
            # Create transaction
            transaction = Transaction(
                document_id=None,  # Manual entry, no document
                transaction_date=transaction_date or datetime.now().date(),
                amount=amount,
                currency=data.get('currency', 'INR'),
                vendor_name=data['vendor_name'].strip(),
                description=data.get('description', 'Manual entry').strip(),
                category_id=data['category_id'],
                payment_method=data.get('payment_method', 'Other'),
                tax_amount=float(data.get('tax_amount', 0.0)),
                tax_percentage=float(data.get('tax_percentage', 0.0)) if data.get('tax_percentage') else None
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            print(f"✅ Transaction created: {transaction.vendor_name} - ₹{transaction.amount}")
            
            return jsonify({
                'success': True,
                'message': 'Transaction created successfully',
                'transaction': transaction.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating transaction: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@app.route('/api/transactions/<int:trans_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def handle_single_transaction(trans_id):
    """Get, update, or delete a specific transaction"""
    
    transaction = Transaction.query.get(trans_id)
    
    if not transaction:
        return jsonify({
            'success': False,
            'error': 'Transaction not found'
        }), 404
    
    if request.method == 'GET':
        # GET - Retrieve single transaction
        return jsonify({
            'success': True,
            'transaction': transaction.to_dict()
        })
    
    elif request.method == 'PUT':
        # PUT - Update transaction
        try:
            data = request.get_json()
            
            # Update fields if provided
            if 'amount' in data:
                amount = float(data['amount'])
                if amount <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'Amount must be positive'
                    }), 400
                transaction.amount = amount
            
            if 'vendor_name' in data:
                transaction.vendor_name = data['vendor_name'].strip()
            
            if 'transaction_date' in data:
                transaction.transaction_date = datetime.strptime(
                    data['transaction_date'], '%Y-%m-%d'
                ).date()
            
            if 'category_id' in data:
                # Validate category
                category = Category.query.get(data['category_id'])
                if not category:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid category ID'
                    }), 400
                transaction.category_id = data['category_id']
            
            if 'description' in data:
                transaction.description = data['description'].strip()
            
            if 'payment_method' in data:
                transaction.payment_method = data['payment_method']
            
            if 'tax_amount' in data:
                transaction.tax_amount = float(data['tax_amount'])
            
            # Update timestamp
            transaction.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            print(f"✅ Transaction updated: {transaction.id}")
            
            return jsonify({
                'success': True,
                'message': 'Transaction updated successfully',
                'transaction': transaction.to_dict()
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating transaction: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'DELETE':
        # DELETE - Remove transaction
        try:
            db.session.delete(transaction)
            db.session.commit()
            
            print(f"✅ Transaction deleted: {trans_id}")
            
            return jsonify({
                'success': True,
                'message': 'Transaction deleted successfully'
            })
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error deleting transaction: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@app.route('/api/transactions/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_transactions():
    """Delete multiple transactions at once"""
    try:
        data = request.get_json()
        transaction_ids = data.get('transaction_ids', [])
        
        if not transaction_ids:
            return jsonify({
                'success': False,
                'error': 'No transaction IDs provided'
            }), 400
        
        # Delete transactions
        deleted_count = Transaction.query.filter(
            Transaction.id.in_(transaction_ids)
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count} transactions deleted',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in bulk delete: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/transactions/import', methods=['POST'])
@login_required
def import_transactions():
    """Import transactions from CSV/Excel file (with auto budget sync)"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        filename = file.filename.lower()
        
        if filename.endswith('.csv'):
            import csv
            from io import StringIO
            
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            transactions_created = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    transaction = Transaction(
                        transaction_date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                        amount=float(row['amount']),
                        vendor_name=row['vendor'],
                        description=row.get('description', 'Imported from CSV'),
                        category_id=int(row.get('category_id', 1)),
                        payment_method=row.get('payment_method', 'Other')
                    )
                    
                    db.session.add(transaction)
                    transactions_created += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            db.session.commit()
            
            # ✅ BATCH SYNC ALL BUDGETS AFTER IMPORT
            from utils.budget_utils import BudgetUtils
            print("🔄 Syncing all budgets after bulk import...")
            updated_count = BudgetUtils.sync_all_budgets()
            print(f"✅ Synced {updated_count} budgets")
            
            return jsonify({
                'success': True,
                'message': f'Imported {transactions_created} transactions',
                'imported_count': transactions_created,
                'budgets_updated': updated_count,
                'errors': errors
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Unsupported file format. Use CSV'
            }), 400
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error importing transactions: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# VALIDATION & UTILITY ENDPOINTS
# ============================================================================

@app.route('/api/transactions/validate-duplicate', methods=['POST'])
@login_required
def validate_duplicate():
    """Check if a transaction might be a duplicate"""
    try:
        data = request.get_json()
        
        # Look for similar transactions (same vendor, amount, within 24 hours)
        similar = Transaction.query.filter(
            Transaction.vendor_name == data['vendor_name'],
            Transaction.amount == float(data['amount'])
        ).all()
        
        if similar:
            return jsonify({
                'success': True,
                'is_duplicate': True,
                'similar_transactions': [t.to_dict() for t in similar[:5]]
            })
        else:
            return jsonify({
                'success': True,
                'is_duplicate': False
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
