import os
from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import bcrypt
import secrets
# import bson
from bson.objectid import ObjectId

app = Flask(__name__)

# Secret key for session management
app.secret_key = secrets.token_hex(32)

# MongoDB Connection
client = MongoClient('mongodb+srv://suhail:suhail123@cluster0.pxc97.mongodb.net/')
db = client['userDB']
users_collection = db['users']
products_collection = db['products']

# Directory to save uploaded images
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ADMIN_CODE="Ghost"

# Home Route
@app.route('/')
def home():
    products = products_collection.find()  # Get all products
    if 'email' in session:
        return render_template('home.html', products=products, name=session.get('firstName'))
    else:
        return redirect(url_for('login'))

# Admin Route (Product List)
@app.route('/admin')
def admin():
    if 'email' in session:
        products = products_collection.find()  # Get all products
        return render_template('admin.html', products=products)
    else:
        return redirect(url_for('login'))

# Signup Route
@app.route('/api/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin')
        admin_code= request.form.get('admin_code')
        
        # Check if user already exists
        user = users_collection.find_one({"email": email})
        if user:
            return "Email already registered!"
        # If trying to sign up as an admin, validate admin code
        if is_admin:
            if admin_code != ADMIN_CODE:
                return "Invalid admin code!"
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert new user into MongoDB
        users_collection.insert_one({
            'firstName': first_name,
            'lastName': last_name,
            'email': email,
            'password': hashed_password,
            'is_admin': bool(is_admin)  # Store if the user is an admin
        })
        
        # Set session after successful signup
        session['email'] = email
        session['firstName'] = first_name
        session['lastName'] = last_name
        session['is_admin'] = bool(is_admin)
        
        if is_admin:
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('home'))
    return render_template('signup.html')

# Login Route
@app.route('/api/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Find user by email
        user = users_collection.find_one({"email": email})
        
        if user:
            # Check if password matches
            if bcrypt.checkpw(password.encode('utf-8'), user['password']):
                # Set session after successful login
                session['email'] = email
                session['firstName'] = user['firstName']
                session['lastName'] = user['lastName']
                session['is_admin'] = user.get('is_admin', False)
                
                # If user is an admin, redirect to admin page
                if session['is_admin']:
                    return redirect(url_for('admin'))
                else:
                    return redirect(url_for('home'))
            else:
                return "Incorrect password!"
        else:
            return "Email not found!"
    return render_template('login.html')

# Add Product Route
@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if 'email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        price = float(request.form.get('price'))
        image = request.files['image']
        description = request.form.get('description')

        # Save the image file
        image_filename = secrets.token_hex(8) + os.path.splitext(image.filename)[1]  # Unique filename
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image.save(image_path)

        # Insert product into MongoDB
        products_collection.insert_one({
            'title': title,
            'price': price,
            'image': url_for('static', filename='uploads/' + image_filename),  # Store the URL
            'description': description
        })
        return redirect(url_for('admin'))

    return render_template('add_product.html')

# Edit Product Route
@app.route('/edit-product/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    product = products_collection.find_one({'_id': ObjectId(product_id)})

    if request.method == 'POST':
        title = request.form.get('title')
        price = float(request.form.get('price'))
        image = request.form.get('image')
        description = request.form.get('description')

        # Update product in MongoDB
        products_collection.update_one(
            {'_id': ObjectId(product_id)},
            {'$set': {
                'title': title,
                'price': price,
                'image': image,
                'description': description
            }}
        )
        return redirect(url_for('admin'))

    return render_template('edit_product.html', product=product)

# Delete Product Route
@app.route('/delete-product/<product_id>')
def delete_product(product_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    # Delete product from MongoDB
    products_collection.delete_one({'_id': ObjectId(product_id)})
    return redirect(url_for('admin'))

# Cart


# Logout Route
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

# Start Flask Server
if __name__ == '__main__':
    app.run(debug=True)