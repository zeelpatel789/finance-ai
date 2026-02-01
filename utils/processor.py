"""
Document Processing Workflow
✅ NOW WITH NOTIFICATION INTEGRATION
"""

from ai_modules.document_processor import DocumentProcessor
from ai_modules.data_extractor import DataExtractor
from ai_modules.categorizer import TransactionCategorizer
from models.database import db
from models.document import Document
from models.transaction import Transaction
from models.category import Category
import os

class DocumentProcessingWorkflow:
    """Complete workflow for processing documents"""
    
    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.data_extractor = DataExtractor()
        self.categorizer = TransactionCategorizer()
        
        # Try to load pre-trained model
        model_path = 'ml_models/category_classifier.pkl'
        if not self.categorizer.load_model(model_path):
            # Train with default data if model doesn't exist
            self.categorizer.train()
            # Save for future use
            os.makedirs('ml_models', exist_ok=True)
            self.categorizer.save_model(model_path)
    
    def process_document(self, document_id):
        """Process a single document"""
        transaction_count = 0
        
        try:
            # Get document from database
            document = db.session.get(Document, document_id)
            
            if not document:
                return False, "Document not found"
            
            if document.processed:
                return False, "Document already processed"
            
            # Step 1: Extract text
            print(f"📄 Processing: {document.original_filename}")
            
            file_extension = document.filename.split('.')[-1].lower()
            text, error = self.doc_processor.process_document(
                document.file_path,
                file_extension
            )
            
            if error:
                return False, error
            
            if not text:
                return False, "No text extracted from document"
            
            # Store raw text
            document.raw_text = text
            
            print(f"✅ Extracted {len(text)} characters")
            
            # Step 2: Extract structured data
            print("🔍 Extracting structured data...")
            
            extracted_data = self.data_extractor.extract_all_data(text)
            
            if not extracted_data:
                document.processed = True
                db.session.commit()
                return False, "Could not extract data from text"
            
            print(f"✅ Extracted: {extracted_data}")
            
            # Step 3: Categorize
            vendor = extracted_data.get('vendor', 'Unknown')
            category_name, confidence = self.categorizer.predict_category(vendor, text)
            
            print(f"🏷️ Category: {category_name} (confidence: {confidence:.1f}%)")
            
            # Get category from database
            category = Category.query.filter_by(name=category_name).first()
            
            if not category:
                category = Category.query.filter_by(name='Other').first()
            
            # Step 4: Create transaction
            amount = extracted_data.get('amount')
            transaction = None
            
            if amount:
                transaction = Transaction(
                    document_id=document.id,
                    transaction_date=extracted_data.get('date'),
                    amount=amount,
                    currency='INR',
                    vendor_name=vendor,
                    description=f"Extracted from {document.original_filename}",
                    category_id=category.id if category else None,
                    payment_method=extracted_data.get('payment_method'),
                    tax_amount=extracted_data.get('tax_amount') or 0.0,
                    tax_percentage=extracted_data.get('tax_percentage')
                )
                
                db.session.add(transaction)
                transaction_count = 1
                print(f"💰 Transaction created: {vendor} - ₹{amount}")
            else:
                print("⚠️ No amount found, transaction not created")
            
            # Mark as processed
            document.processed = True
            db.session.commit()
            
            # ✅ AUTO-SYNC BUDGET (if transaction was created)
            if amount and transaction:
                from utils.budget_utils import BudgetUtils
                BudgetUtils.sync_transaction_budgets(transaction)
                print(f"✅ Budget synced for {category.name if category else 'Unknown'}")
            
            # ✅ NOTIFICATION: Document processed successfully
            try:
                from models.notification_system import BudgetNotificationManager
                BudgetNotificationManager.notify_document_processed(document, transaction_count)
                print(f"✅ Notification sent: Document processed")
            except Exception as e:
                print(f"⚠️ Notification error (non-critical): {e}")
            
            # ✅ NOTIFICATION: Transaction added
            if transaction:
                try:
                    from models.notification_system import BudgetNotificationManager
                    BudgetNotificationManager.notify_transaction_added(transaction)
                    print(f"✅ Notification sent: Transaction added")
                except Exception as e:
                    print(f"⚠️ Notification error (non-critical): {e}")
            
            return True, "Document processed successfully"
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error processing document: {e}")
            import traceback
            traceback.print_exc()
            
            # ✅ NOTIFICATION: Processing failed
            try:
                from models.notification_system import NotificationManager
                NotificationManager.create_notification(
                    type='document_processing_failed',
                    severity='danger',
                    title='❌ Document Processing Failed',
                    message=f'Failed to process document: {str(e)[:100]}',
                    action_url='/upload',
                    action_label='View Documents'
                )
            except Exception as notify_error:
                print(f"⚠️ Could not send failure notification: {notify_error}")
            
            return False, str(e)
    
    def process_multiple_documents(self, document_ids):
        """
        Process multiple documents in batch
        ✅ WITH BATCH NOTIFICATION
        """
        results = {
            'success': [],
            'failed': [],
            'total_transactions': 0
        }
        
        for doc_id in document_ids:
            success, message = self.process_document(doc_id)
            
            if success:
                results['success'].append(doc_id)
                # Count transactions created
                document = db.session.get(Document, doc_id)
                if document:
                    trans_count = Transaction.query.filter_by(document_id=doc_id).count()
                    results['total_transactions'] += trans_count
            else:
                results['failed'].append({'id': doc_id, 'error': message})
        
        # ✅ NOTIFICATION: Batch processing complete
        if results['success']:
            try:
                from models.notification_system import NotificationManager
                NotificationManager.create_notification(
                    type='batch_processing_complete',
                    severity='success',
                    title='📄 Batch Processing Complete',
                    message=f"Successfully processed {len(results['success'])} document(s), extracted {results['total_transactions']} transaction(s)",
                    action_url='/upload',
                    action_label='View Documents'
                )
            except Exception as e:
                print(f"⚠️ Notification error: {e}")
        
        return results