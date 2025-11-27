from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os, json, uuid, shutil, xml.etree.ElementTree as ET
import PyPDF2  # For better language detection

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-super-secret-key-change-this-1234567890'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'epub', 'mobi'}
app.config['ALLOWED_IMAGES'] = {'jpg', 'jpeg', 'png', 'webp'}

db = SQLAlchemy(app)

# COMPLETE LANGUAGE MAP - All your languages with 2 and 3 letter codes
LANGUAGE_MAP = {
    # Arabic
    'ar':'Arabic','ara':'Arabic',
    # Bulgarian
    'bg':'Bulgarian','bul':'Bulgarian','bg-BG':'Bulgarian',
    # Catalan
    'ca':'Catalan','cat':'Catalan',
    # Czech
    'cs':'Czech','ces':'Czech','cze':'Czech','cs-CZ':'Czech',
    # Danish
    'da':'Danish','dan':'Danish','da-DK':'Danish',
    # German
    'de':'German','deu':'German','ger':'German','de-DE':'German',
    # Greek
    'el':'Greek','ell':'Greek','gre':'Greek','el-GR':'Greek',
    # English
    'en':'English','eng':'English','en-US':'English','en-GB':'English',
    # Spanish
    'es':'Spanish','spa':'Spanish','es-ES':'Spanish',
    # Estonian
    'et':'Estonian','est':'Estonian','et-EE':'Estonian',
    # Finnish
    'fi':'Finnish','fin':'Finnish','fi-FI':'Finnish',
    # French
    'fr':'French','fra':'French','fre':'French','fr-FR':'French',
    # Croatian
    'hr':'Croatian','hrv':'Croatian','hr-HR':'Croatian',
    # Hungarian
    'hu':'Hungarian','hun':'Hungarian','hu-HU':'Hungarian',
    # Italian
    'it':'Italian','ita':'Italian','it-IT':'Italian',
    # Japanese
    'ja':'Japanese','jpn':'Japanese','ja-JP':'Japanese',
    # Korean
    'ko':'Korean','kor':'Korean','ko-KR':'Korean',
    # Lithuanian
    'lt':'Lithuanian','lit':'Lithuanian','lt-LT':'Lithuanian',
    # Latvian
    'lv':'Latvian','lav':'Latvian','lv-LV':'Latvian',
    # Dutch
    'nl':'Dutch','nld':'Dutch','dut':'Dutch','nl-NL':'Dutch',
    # Polish
    'pl':'Polish','pol':'Polish','pl-PL':'Polish',
    # Portuguese
    'pt':'Portuguese','por':'Portuguese','pt-PT':'Portuguese','pt-BR':'Portuguese',
    # Romanian
    'ro':'Romanian','ron':'Romanian','rum':'Romanian','ro-RO':'Romanian',
    # Russian
    'ru':'Russian','rus':'Russian','ru-RU':'Russian',
    # Swedish
    'sv':'Swedish','swe':'Swedish','sv-SE':'Swedish',
    # Turkish
    'tr':'Turkish','tur':'Turkish','tr-TR':'Turkish',
    # Ukrainian
    'uk':'Ukrainian','ukr':'Ukrainian','uk-UA':'Ukrainian',
    # Chinese
    'zh':'Chinese','chi':'Chinese','zho':'Chinese','zh-CN':'Chinese','zh-TW':'Chinese'
}

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(200))
    description = db.Column(db.Text)
    category = db.Column(db.String(100), default='General')
    language = db.Column(db.String(50), default='English')
    filename = db.Column(db.String(200), nullable=False)
    cover_image = db.Column(db.String(200))
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)

def get_setting(k, d=''): s=Settings.query.filter_by(key=k).first(); return s.value if s else d
def set_setting(k, v): s=Settings.query.filter_by(key=k).first() or Settings(key=k); s.value=v; db.session.add(s); db.session.commit()

# IMPROVED: Better language detection from PDF metadata
def detect_language_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            pdf = PyPDF2.PdfReader(f)
            if pdf.metadata:
                # Check PDF metadata for language
                lang = pdf.metadata.get('/Language', '').lower()
                if lang:
                    lang_code = lang[:3] if len(lang) >= 3 else lang[:2]
                    return LANGUAGE_MAP.get(lang_code, lang.title())
    except:
        pass
    return None

# IMPROVED: Better metadata extraction with OPF support
def extract_metadata(book_path, book_filename, cover_file=None):
    base = book_filename.rsplit('.', 1)[0]
    meta = {
        'title': base.replace('_', ' ').replace('-', ' '),
        'author': '',
        'description': '',
        'category': 'General',
        'language': 'English',
        'cover_filename': None
    }

    # MANUAL COVER — SAVED DIRECTLY
    if cover_file and cover_file.filename:
        ext = cover_file.filename.rsplit('.', 1)[-1].lower()
        if ext in app.config['ALLOWED_IMAGES']:
            cover_filename = f"{uuid.uuid4()}_cover.{ext}"
            cover_path = os.path.join(app.config['UPLOAD_FOLDER'], 'covers', cover_filename)
            os.makedirs(os.path.dirname(cover_path), exist_ok=True)
            cover_file.save(cover_path)
            meta['cover_filename'] = cover_filename

    # OPF FILE DETECTION - Check same folder AND parent folder
    folder = os.path.dirname(book_path)
    opf_candidates = [
        os.path.join(folder, f"{base}.opf"),  # Same name as book
        os.path.join(folder, "metadata.opf"),  # Generic name
        os.path.join(os.path.dirname(folder), f"{base}.opf"),  # Parent folder
    ]
    
    opf_path = None
    for candidate in opf_candidates:
        if os.path.exists(candidate):
            opf_path = candidate
            break

    if opf_path:
        try:
            tree = ET.parse(opf_path)
            root = tree.getroot()
            ns = {'dc': 'http://purl.org/dc/elements/1.1/', 'opf': 'http://www.idpf.org/2007/opf'}
            
            # Extract all metadata
            title = root.findtext('.//dc:title', None, ns)
            if title: meta['title'] = title
            
            author = root.findtext('.//dc:creator', None, ns)
            if author: meta['author'] = author
            
            desc = root.findtext('.//dc:description', None, ns)
            if desc: meta['description'] = desc
            
            # Better language detection from OPF
            lang = root.findtext('.//dc:language', None, ns)
            if lang:
                lang_clean = lang.strip().lower()[:3]
                detected = LANGUAGE_MAP.get(lang_clean)
                if detected:
                    meta['language'] = detected
            
            # Category from subject
            subjects = root.findall('.//dc:subject', ns)
            if subjects and subjects[0].text:
                meta['category'] = subjects[0].text.strip().title()
                
            print(f"✓ OPF loaded: {os.path.basename(opf_path)} → {meta['title']}")
        except Exception as e:
            print(f"✗ OPF parse error: {e}")

    # Fallback: Try PDF metadata for language
    if meta['language'] == 'English' and book_path.endswith('.pdf'):
        pdf_lang = detect_language_from_pdf(book_path)
        if pdf_lang:
            meta['language'] = pdf_lang

    return meta

@app.route('/')
def index():
    cats = sorted({b.category for b in Book.query.all() if b.category})
    langs = sorted({b.language for b in Book.query.all() if b.language})
    donation_links = json.loads(get_setting('donation_links','[]'))
    return render_template('index.html', categories=cats, languages=langs, donation_links=donation_links)

@app.route('/book/<int:book_id>')
def book_page(book_id):
    book = Book.query.get_or_404(book_id)
    donation_links = json.loads(get_setting('donation_links','[]'))
    return render_template('book_page.html', book=book, donation_links=donation_links)

# IMPROVED: Better search with partial matches
@app.route('/api/books')
def api_books():
    q = Book.query
    if request.args.get('category'): 
        q = q.filter_by(category=request.args.get('category'))
    if request.args.get('language'): 
        q = q.filter_by(language=request.args.get('language'))
    if request.args.get('search'):
        s = f"%{request.args.get('search')}%"
        q = q.filter(db.or_(
            Book.title.ilike(s), 
            Book.author.ilike(s),
            Book.description.ilike(s)  # Also search descriptions
        ))
    books = q.order_by(Book.upload_date.desc()).all()
    return jsonify([{
        'id': b.id, 'title': b.title, 'author': b.author or 'Unknown Author',
        'description': b.description or '', 'category': b.category, 'language': b.language,
        'cover_image': url_for('get_cover', book_id=b.id) if b.cover_image else None,
        'download_count': b.download_count
    } for b in books])

@app.route('/download/<int:book_id>')
def download_book(book_id):
    b = Book.query.get_or_404(book_id)
    path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', b.filename)
    return send_file(path, as_attachment=True, download_name=f"{b.title}.{b.filename.rsplit('.', 1)[-1]}")

@app.route('/cover/<int:book_id>')
def get_cover(book_id):
    b = Book.query.get_or_404(book_id)
    if b.cover_image:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], 'covers', b.cover_image))
    abort(404)

@app.route('/api/collect-email', methods=['POST'])
def collect_email():
    data = request.get_json()
    email = data.get('email')
    book_id = data.get('book_id')
    book = Book.query.get(book_id)
    if book and email:
        e = Email.query.filter_by(email=email).first()
        if e:
            e.download_count += 1
        else:
            e = Email(email=email, download_count=1)
            db.session.add(e)
        book.download_count += 1
        db.session.commit()
        return jsonify({'success': True, 'download_url': url_for('download_book', book_id=book_id)})
    return jsonify({'error': 'Invalid'}), 400

@app.route('/admin')
def admin():
    if 'admin_logged_in' not in session: return redirect(url_for('admin_login'))
    books = Book.query.order_by(Book.upload_date.desc()).all()
    donation_links = json.loads(get_setting('donation_links','[]'))
    return render_template('admin.html', books=books, donation_links=donation_links)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = Admin.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['admin_logged_in'] = True
            return redirect('/admin')
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/')

@app.route('/admin/upload', methods=['POST'])
def upload_books():
    if 'admin_logged_in' not in session: return jsonify({'error':'Unauthorized'}), 401
    books = request.files.getlist('books')
    covers = request.files.getlist('covers')
    opf_files = request.files.getlist('opf')  # NEW: Accept OPF files
    results = []
    cover_index = 0
    opf_index = 0

    for i, book_file in enumerate(books):
        if not book_file or not book_file.filename: continue
        if book_file.filename.rsplit('.', 1)[-1].lower() not in app.config['ALLOWED_EXTENSIONS']: continue

        filename = secure_filename(book_file.filename)
        unique = f"{uuid.uuid4()}_{filename}"
        book_path = os.path.join(app.config['UPLOAD_FOLDER'], 'books', unique)
        os.makedirs(os.path.dirname(book_path), exist_ok=True)
        book_file.save(book_path)

        # Save OPF file temporarily for metadata extraction
        if opf_index < len(opf_files) and opf_files[opf_index].filename:
            opf_temp = os.path.join(os.path.dirname(book_path), f"{filename.rsplit('.', 1)[0]}.opf")
            opf_files[opf_index].save(opf_temp)
            opf_index += 1

        # Pair with cover
        matched_cover = None
        if cover_index < len(covers) and covers[cover_index].filename:
            matched_cover = covers[cover_index]
            cover_index += 1

        meta = extract_metadata(book_path, filename, matched_cover)

        book = Book(
            title=meta['title'],
            author=meta['author'],
            description=meta['description'],
            category=meta['category'],
            language=meta['language'],
            filename=unique,
            cover_image=meta['cover_filename'],
            file_size=os.path.getsize(book_path)
        )
        db.session.add(book)
        results.append({
            'success': True, 
            'title': meta['title'], 
            'has_cover': bool(meta['cover_filename']),
            'language': meta['language'],
            'has_description': bool(meta['description'])
        })

    db.session.commit()
    return jsonify(results)

# IMPROVED: Better edit handling with validation
@app.route('/admin/book/<int:book_id>', methods=['PUT', 'DELETE'])
def manage_book(book_id):
    if 'admin_logged_in' not in session: return jsonify({'error':'Unauthorized'}), 401
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'DELETE':
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'books', book.filename))
            if book.cover_image:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], 'covers', book.cover_image))
        except: pass
        db.session.delete(book)
        db.session.commit()
        return jsonify({'success': True})
    
    if request.method == 'PUT':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            # Update fields with validation
            if 'title' in data and data['title'].strip():
                book.title = data['title'].strip()
            if 'author' in data:
                book.author = data['author'].strip() if data['author'] else ''
            if 'description' in data:
                book.description = data['description'].strip() if data['description'] else ''
            if 'category' in data and data['category'].strip():
                book.category = data['category'].strip()
            if 'language' in data and data['language'].strip():
                book.language = data['language'].strip()
            
            db.session.commit()
            return jsonify({
                'success': True, 
                'book': {
                    'id': book.id,
                    'title': book.title,
                    'author': book.author,
                    'description': book.description,
                    'category': book.category,
                    'language': book.language
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    if 'admin_logged_in' not in session: return jsonify({'error':'Unauthorized'}), 401
    data = request.get_json()
    set_setting('donation_links', json.dumps(data.get('donation_links', [])))
    return jsonify({'success': True})

with app.app_context():
    db.create_all()
    if not Admin.query.first():
        db.session.add(Admin(username='citify', password_hash=generate_password_hash('Citation6-Outweigh7-Worried8-Unneeded0-Eccentric7')))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
