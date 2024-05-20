import openfoodfacts
import json
import re
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

from mapping import additive_name, group_name, grade_color, score_color
from utils import filter_ingredient, analyse_nutrient, filter_image
from database import database_history, database_search
from authentication import auth_blueprint

app = Flask(__name__)
app.secret_key = '1234567890'
app.register_blueprint(auth_blueprint)

CORS(app, resources={r'/api/*': {'origins': ['*']}})
api = openfoodfacts.API(user_agent='ScanEasy/1.6')

@app.route('/api/v1/search/barcode', methods=['POST'])
def barcode_search():
    start_time = datetime.now()

    product_barcode = request.json.get('product_barcode')
    required_data = json.load(open('product_schema.json'))
    product_data = api.product.get(product_barcode, fields=required_data)

    if not product_data:
        return jsonify({'error': 'Product not found.'})

    missing_fields = set(required_data) - set(product_data.keys())
    for field in missing_fields:
        print(f'Warning: Data for "{field}" is missing.')

    product_data['additives_tags'] = [
        tag
        for tag in product_data['additives_tags']
        if not tag.endswith('i')
    ]

    product_data = {
        key: [
            re.sub(r'^en:', '', item) if isinstance(item, str) else item
            for item in value
        ]
        if isinstance(value, list) else re.sub(r'^en:', '', value)
        if isinstance(value, str) else value
        for key, value in product_data.items()
    }

    end_time = datetime.now()
    response_time = (end_time - start_time).total_seconds()
    response_size = sys.getsizeof(product_data) / 1024

    product_data.update(
        {
            'search_type': 'Open Food Facts API',
            'search_response': '200 OK',
            'response_time': f'{response_time:.2f} seconds',
            'response_size': f'{response_size:.2f} KB',
            'search_date': datetime.now().strftime('%d-%B-%Y'),
            'search_time': datetime.now().strftime('%I:%M %p'),
            'additives_names': additive_name(product_data['additives_tags'], json.load(open('additive_names.json'))),
            'ingredients': filter_ingredient(product_data['ingredients']),
            'nova_group_name': group_name(product_data['nova_group']),
            'nutriments': analyse_nutrient(product_data['nutriments'], json.load(open('nutrient_limits.json'))),
            'nutriscore_grade_color': grade_color(product_data['nutriscore_grade']),
            'nutriscore_score_color': score_color(product_data['nutriscore_score']),
            'selected_images': filter_image(product_data['selected_images'])
        }
    )

    database_history(product_barcode, product_data)

    return jsonify(product_data)

# @app.route('/api/v1/search/text', methods=['POST'])
# def text_search():
#     product_name = request.form.get('product_name')
#     product_data = api.product.text_search(product_name)

#     if not product_data:
#         return jsonify({'error': 'Product not found.'})

#     return jsonify(product_data)


@app.route('/api/v1/search/database', methods=['POST'])
def database_search():
    start_time = datetime.now()

    product_keyword = request.json.get('product_keyword')
    search_keys = ['_keywords', 'brands', 'categories', 'product_name']
    product_data = database_search(product_keyword, search_keys)

    if not product_data:
        return jsonify({'error': 'Product not found.'})

    end_time = datetime.now()
    response_time = (end_time - start_time).total_seconds()
    response_size = sys.getsizeof(product_data) / 1024

    product_data.append(
        {
            'search_type': 'Google Firestore Database',
            'search_response': '200 OK',
            'response_time': f'{response_time:.2f} seconds',
            'response_size': f'{response_size:.2f} KB',
            'search_date': datetime.now().strftime('%d-%B-%Y'),
            'search_time': datetime.now().strftime('%I:%M %p')
        }
    )

    return jsonify(product_data)

if __name__ == '__main__':
    app.run(debug=True)
