from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import PyPDF2
import ebooklib
from ebooklib import epub
from langdetect import detect
from lxml import etree

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-change-this-1234567890'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

db = SQLAlchemy(app)

# Supported languages
SUPPORTED_LANGUAGES = [
    'ar', 'bg', 'ca', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr',
    'hr', 'hu', 'it', 'ja', 'ko', 'lt', 'lv', 'nl', 'pl', 'pt', 'ro', 'ru',
    'sv', 'tr', 'uk', 'zh-cn'
]

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    author = db.Column(db.String(200))
    description = db.Column(db.Text)
    language = db.Column(db.String(10))
    filename = db.Column(db.String(500), nullable=False)
    cover_image = db.Column(db.String(500))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_type = db.Column(db.String(10))

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    download_date = db.Column(db.DateTime, default=datetime.utcnow)

# Route to serve uploaded files
@app.route('/uploads/<path:subpath>/<filename>')
def serve_uploads(subpath, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], subpath), filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'epub'}

def extract_metadata_from_opf(opf_path):
    """Extract metadata from .opf file (Calibre format)"""
    try:
        tree = etree.parse(opf_path)
        root = tree.getroot()
        ns = {'dc': 'http://purl.org/dc/elements/1.1/', 
              'opf': 'http://www.idpf.org/2007/opf'}
        
        metadata = {}
        title = root.find('.//dc:title', ns)
        if title is not None and title.text:
            metadata['title'] = title.text
        
        creator = root.find('.//dc:creator', ns)
        if creator is not None and creator.text:
            metadata['author'] = creator.text
        
        description = root.find('.//dc:description', ns)
        if description is not None and description.text:
            metadata['description'] = description.text
        
        language = root.find('.//dc:language', ns)
        if language is not None and language.text:
            metadata['language'] = language.text
        
        return metadata
    except:
        return {}

def extract_pdf_metadata(file_path):
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            metadata = pdf_reader.metadata
            
            info = {}
            if metadata:
                info['title'] = metadata.get('/Title', '')
                info['author'] = metadata.get('/Author', '')
            
            # Try to extract text for language detection
            if len(pdf_reader.pages) > 0:
                text = pdf_reader.pages[0].extract_text()[:500]
                if text:
                    try:
                        detected_lang = detect(text)
                        if detected_lang in SUPPORTED_LANGUAGES:
                            info['language'] = detected_lang
                    except:
                        pass
            
            return info
    except:
        return {}

def extract_epub_metadata(file_path):
    try:
        book = epub.read_epub(file_path)
        info = {}
        
        info['title'] = book.get_metadata('DC', 'title')
        if info['title']:
            info['title'] = info['title'][0][0] if info['title'] else ''
        
        info['author'] = book.get_metadata('DC', 'creator')
        if info['author']:
            info['author'] = info['author'][0][0] if info['author'] else ''
        
        info['description'] = book.get_metadata('DC', 'description')
        if info['description']:
            info['description'] = info['description'][0][0] if info['description'] else ''
        
        info['language'] = book.get_metadata('DC', 'language')
        if info['language']:
            lang = info['language'][0][0] if info['language'] else ''
            if lang in SUPPORTED_LANGUAGES:
                info['language'] = lang
        
        return info
    except:
        return {}

def extract_epub_cover(file_path, cover_filename):
    try:
        book = epub.read_epub(file_path)
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER or 'cover' in item.get_name().lower():
                cover_path = os.path.join(app.config['UPLOAD_FOLDER'], 'covers', cover_filename)
                with open(cover_path, 'wb') as f:
                    f.write(item.get_content())
                return cover_filename
    except:
        pass
    return None

@app.route('/')
def index():
    search_query = request.args.get('search', '')
    language_filter = request.args.get('language', '')
    
    query = Book.query
    
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Book.title.ilike(search_pattern),
                Book.author.ilike(search_pattern),
                Book.description.ilike(search_pattern)
            )
        )
    
    if language_filter:
        query = query.filter(Book.language == language_filter)
    
    books = query.order_by(Book.upload_date.desc()).all()
    
    # Get unique languages for filter
    languages = db.session.query(Book.language).distinct().all()
    languages = [lang[0] for lang in languages if lang[0]]
    
    return render_template('index.html', books=books, search_query=search_query, 
                         languages=languages, selected_language=language_filter)

@app.route('/book/<int:book_id>')
def book_page(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_page.html', book=book)

@app.route('/download/<int:book_id>', methods=['POST'])
def download_book(book_id):
    book = Book.query.get_or_404(book_id)
    email = request.form.get('email')
    
    if not email:
        flash('Email is required to download', 'error')
        return redirect(url_for('book_page', book_id=book_id))
    
    # Record the download
    download = Download(book_id=book_id, email=email)
    db.session.add(download)
    db.session.commit()
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', book.filename)
    return send_file(file_path, as_attachment=True, download_name=book.filename)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'Citation6-Outweigh7-Worried8-Unneeded0-Eccentric7':
            return redirect(url_for('admin_panel'))
        else:
            flash('Incorrect password', 'error')
    
    return render_template('login.html')

@app.route('/admin/panel')
def admin_panel():
    books = Book.query.order_by(Book.upload_date.desc()).all()
    total_downloads = Download.query.count()
    return render_template('admin.html', books=books, total_downloads=total_downloads)

@app.route('/admin/upload', methods=['POST'])
def upload_book():
    if 'book_file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin_panel'))
    
    file = request.files['book_file']
    opf_file = request.files.get('opf_file')
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_panel'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', filename)
        file.save(file_path)
        
        file_type = filename.rsplit('.', 1)[1].lower()
        
        # Extract metadata
        metadata = {}
        if opf_file and opf_file.filename.endswith('.opf'):
            opf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp.opf')
            opf_file.save(opf_path)
            metadata = extract_metadata_from_opf(opf_path)
            os.remove(opf_path)
        elif file_type == 'pdf':
            metadata = extract_pdf_metadata(file_path)
        elif file_type == 'epub':
            metadata = extract_epub_metadata(file_path)
        
        # Handle cover image
        cover_filename = None
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            cover_file = request.files['cover_image']
            cover_filename = secure_filename(f"cover_{filename.rsplit('.', 1)[0]}.jpg")
            cover_path = os.path.join(app.config['UPLOAD_FOLDER'], 'covers', cover_filename)
            cover_file.save(cover_path)
        elif file_type == 'epub':
            cover_filename = extract_epub_cover(file_path, f"cover_{filename.rsplit('.', 1)[0]}.jpg")
        
        # Create book entry
        book = Book(
            title=request.form.get('title') or metadata.get('title', filename),
            author=request.form.get('author') or metadata.get('author', 'Unknown'),
            description=request.form.get('description') or metadata.get('description', ''),
            language=request.form.get('language') or metadata.get('language', 'en'),
            filename=filename,
            cover_image=cover_filename,
            file_type=file_type
        )
        
        db.session.add(book)
        db.session.commit()
        
        flash(f'Book "{book.title}" uploaded successfully!', 'success')
    else:
        flash('Invalid file type. Only PDF and EPUB allowed.', 'error')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit/<int:book_id>', methods=['POST'])
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    
    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    description = request.form.get('description', '').strip()
    language = request.form.get('language', '').strip()
    
    if not title:
        flash('Title cannot be empty', 'error')
        return redirect(url_for('admin_panel'))
    
    book.title = title
    book.author = author if author else 'Unknown'
    book.description = description
    book.language = language if language else 'en'
    
    db.session.commit()
    flash(f'Book "{book.title}" updated successfully!', 'success')
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    
    # Delete files
    book_path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', book.filename)
    if os.path.exists(book_path):
        os.remove(book_path)
    
    if book.cover_image:
        cover_path = os.path.join(app.config['UPLOAD_FOLDER'], 'covers', book.cover_image)
        if os.path.exists(cover_path):
            os.remove(cover_path)
    
    # Delete download records
    Download.query.filter_by(book_id=book_id).delete()
    
    # Delete book
    db.session.delete(book)
    db.session.commit()
    
    flash(f'Book "{book.title}" deleted successfully!', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False)
