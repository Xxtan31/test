from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask import render_template
import threading
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///keys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Key(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False)
    hwid = db.Column(db.String(50), nullable=True)
    usage_limit = db.Column(db.Integer, default=1)
    expiration_date = db.Column(db.DateTime)
    uses = db.Column(db.Integer, default=0)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

# Key oluşturma endpointi
@app.route('/create_key', methods=['POST'])
def create_key():
    data = request.json
    key = data.get('key')
    usage_limit = data.get('usage_limit', 1)
    expiration_minutes = data.get('expiration_minutes', 60)
    expiration_date = datetime.now() + timedelta(minutes=expiration_minutes)
    
    new_key = Key(key=key, usage_limit=usage_limit, expiration_date=expiration_date)
    db.session.add(new_key)
    db.session.commit()
    
    return jsonify({"message": "Key created successfully"}), 201





# Key kullanma endpointi (HWID ile ilişkilendirir)
@app.route('/use_key', methods=['POST'])
def use_key():
    data = request.json
    key = data.get('key')
    hwid = data.get('hwid')
    key_entry = Key.query.filter_by(key=key).first()
    
    if not key_entry:
        return jsonify({"message": "Key not found"}), 404
    
    if key_entry.hwid and key_entry.hwid != hwid:
        return jsonify({"message": "HWID does not match"}), 403
    
    # Süre kontrolü
    if datetime.now() > key_entry.expiration_date:
        db.session.delete(key_entry)
        db.session.commit()
        return jsonify({"message": "Key expired and deleted"}), 403
    
    if key_entry.uses >= key_entry.usage_limit:
        return jsonify({"message": "Key usage limit reached"}), 403
    
    key_entry.uses += 1
    key_entry.hwid = hwid
    db.session.commit()
    return jsonify({"message": "Key used successfully"}), 200

@app.route('/check_hwid', methods=['POST'])
def check_hwid():
    data = request.json
    hwid = data.get('hwid')
    key_entry = Key.query.filter_by(hwid=hwid).first()

    if not key_entry:
        return jsonify({"message": "HWID not found"}), 404

    if datetime.now() > key_entry.expiration_date:
        db.session.delete(key_entry)
        db.session.commit()
        return jsonify({"message": "Key expired and deleted"}), 403

    return jsonify({"message": "HWID valid", "key": key_entry.key}), 200

@app.route('/delete_all_keys', methods=['DELETE'])
def delete_all_keys():
    try:
        num_deleted = db.session.query(Key).delete()
        db.session.commit()
        return jsonify({"message": f"{num_deleted} keys deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Failed to delete keys", "error": str(e)}), 500
        
@app.route('/keys', methods=['GET'])
def get_keys():
    keys = Key.query.all()
    keys_list = [
        {
            "id": key.id,
            "key": key.key,
            "hwid": key.hwid,
            "usage_limit": key.usage_limit,
            "expiration_date": key.expiration_date,
            "uses": key.uses,
        }
        for key in keys
    ]
    return jsonify(keys_list), 200

def delete_expired_keys():
    with app.app_context():
        while True:
            now = datetime.now()
            expired_keys = Key.query.filter(Key.expiration_date < now).all()
            for key in expired_keys:
                db.session.delete(key)
            db.session.commit()
            time.sleep(1)  # Her 1 saniyede bir kontrol et

if __name__ == '__main__':
    threading.Thread(target=delete_expired_keys, daemon=True).start()
    app.run(debug=True)
