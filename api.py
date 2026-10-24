from flask import Flask, jsonify, request, url_for
import os
from werkzeug.utils import secure_filename
from database import TyreDatabase
from extractor import Extractor
from errors import *

upload_folder = "/uploads/"
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = upload_folder

db_file = 'tyres.db'

FILTER_TYPES = {
    "brand": str,
    "prefix": str,
    "width": int,
    "ratio": int,
    "rim_size": int,
    "pattern": str,
    "mrp": float,
    "rcp": float,
    "invoice_price": float,
}

FILTER_TYPES = dict(sorted(FILTER_TYPES.items(), key = lambda fil: fil[0]))

def allowed_filename(filename):
    return '.' in filename and filename.rsplit('.')[1].lower() == 'xlsx'
def get_page_url(page, args):
    args["page"] = page
    return url_for("tyre_search", **args)

@app.get("/api/tyres/search")
def tyre_search():
    result = {}
    args = request.args.to_dict()
    order = args.pop("order", "asc").lower()
    sort_by = args.pop("sort_by", "rim_size")

    if order not in {"asc", "desc"}:
        return jsonify({"error": "order must be asc or desc"}), 400
    if sort_by not in FILTER_TYPES:
        return jsonify({"error": "Invalid sort_by field"}), 400
    if "page" in args:
        try:
            page = int(args.pop('page', 1))
        except ValueError:
            return jsonify({'error': 'Page number must be an int'}), 400

    else:
        page = 1

    if page < 1:
        return jsonify({"error": "Page number can't be negative"}), 400

    filters = {}

    invalid_args = args.keys() - FILTER_TYPES

    if len(invalid_args) > 0:
        return jsonify({"error": "Invalid args provided. The args are: {FILTER_TYPES}"}), 400

    for fil in args:
        try:
            filters[fil] = FILTER_TYPES[fil](args[fil])
        except ValueError:
            return jsonify({"error": f"Invalid type for {fil}"}), 400

    filters['page'] = page
    db = TyreDatabase(db_file)
    rows = db.search(order_by= sort_by, ascending=(order == "asc"), **filters)
    db.close()

    has_next = len(rows) > db.PAGE_SIZE
    data = [tyre.to_dict() for i, tyre in enumerate(rows) if i < db.PAGE_SIZE]
    
    result['data'] = data

    result['length'] = len(data)

    result['page'] = page

    result['previous'] = None if page == 1 else get_page_url(page-1, request.args.to_dict())

    result['next'] = get_page_url(page+1, request.args.to_dict()) if has_next else None

    result['has_next'] = has_next

    return jsonify(result), 200

@app.post("/api/tyres/import")
def tyre_import():
    args = request.args.to_dict()
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400

    file = request.files['file']

    if file.filename == '' or file.filename == None:
        return jsonify({'error': 'No file selected.'}), 400
    
    if not(file and allowed_filename(file.filename)):
        return jsonify({'error': 'File type not supported, only upload xlsx files please.'}), 400 

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    brand_name = args.pop('brand', None)
    if brand_name == None:
       return jsonify({'error': 'Brand name column not provided.'}), 400
    file.save(file_path)
    
    try:
        ex = Extractor(file_path, brand_name, args)
    except MissingFieldError as e:
        return jsonify({'error': e})

    try:
        tyre_set, failed = ex.extract()
        db = TyreDatabase(db_file)
        db.import_tyres(tyre_set)
        db.close()
    except Exception as e:
        return jsonify({'error': e})
    return {'total_count': len(tyre_set)+len(failed), 'succesful': len(tyre_set), 'failed': len(failed)} , 200
