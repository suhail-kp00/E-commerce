import os
from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
import bcrypt
import secrets
# import bson
from bson.objectid import ObjectId
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Secret key for session management
app.secret_key = secrets.token_hex(32)

# MongoDB Connection
client = MongoClient()
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
# Profile
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        return redirect(url_for('login'))

    user = users_collection.find_one({'email': session['email']})

    if request.method == 'POST':
        address = request.form.get('address')
        phone = request.form.get('phone')
        bio = request.form.get('bio')
        profile_pic = request.files.get('profile_pic')

        update_data = {
            'address': address,
            'phone': phone,
            'bio': bio
        }

        # Save profile picture if uploaded
        if profile_pic and profile_pic.filename:
            image_filename = secrets.token_hex(8) + os.path.splitext(profile_pic.filename)[1]
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            profile_pic.save(image_path)
            update_data['profile_pic'] = url_for('static', filename='uploads/' + image_filename)

        users_collection.update_one({'email': session['email']}, {'$set': update_data})
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


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
        products =list(products_collection.find())  # Get all products
        pending_sellers = list(users_collection.find({'role': 'seller', 'is_approved': False}))
        users = list(users_collection.find())
        return render_template('admin.html',users=users, products=products, pending_sellers=pending_sellers)
    else:
        return redirect(url_for('login'))
# edit users
@app.route('/delete-user/<user_id>')
def delete_user(user_id):
    if 'email' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(user_id)})

    if not user:
        return "User not found!"

    # If it's a seller, delete all their products
    if user['role'] == 'seller':
        products_collection.delete_many({'owner_email': user['email']})

    # Delete the user account
    users_collection.delete_one({'_id': ObjectId(user_id)})

    return redirect(url_for('admin'))


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
        role = request.form.get('role')  # 'user', 'admin', or 'seller'
        is_approved = False


        # Check if user already exists
        user = users_collection.find_one({"email": email})
        if user:
            return "Email already registered!"
        if role == 'admin' and admin_code != ADMIN_CODE:
            return "Invalid admin code!"

        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert new user into MongoDB
        users_collection.insert_one({
            'firstName': first_name,
            'lastName': last_name,
            'email': email,
            'password': hashed_password,
            'role': role,
            'is_approved': role != 'seller',  # Sellers need approval
            "address": "",
            "phone": "",
            "bio": "",
            "profile_pic": ""
        })
        
        # Set session after successful signup
        session['email'] = email
        session['firstName'] = first_name
        session['lastName'] = last_name
        session['role'] = role
        session['is_approved'] = role != 'seller'
    
        if role == 'admin':
            return redirect(url_for('admin'))
        elif role == 'seller':
            return "Your account is pending admin approval."
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
                session['role'] = user['role']

                if user['role'] == 'seller':
                    if not user.get('is_approved', False):
                        return "Your seller account is pending admin approval."
                    return redirect(url_for('seller_dashboard'))
                elif user['role'] == 'admin':
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
            'description': description,
            'owner_email': session['email']  # Track who added it
        })
        if session.get('role') == 'admin':
            return redirect(url_for('admin'))
        elif session.get('role') == 'seller':
            return redirect(url_for('seller_dashboard'))
        else:
            return redirect(url_for('home'))

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
        if session.get('role') == 'admin':
            return redirect(url_for('admin'))
        elif session.get('role') == 'seller':
            return redirect(url_for('seller_dashboard'))
        else:
            return redirect(url_for('home'))

    return render_template('edit_product.html', product=product)

# Delete Product Route
@app.route('/delete-product/<product_id>')
def delete_product(product_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    # Delete product from MongoDB
    products_collection.delete_one({'_id': ObjectId(product_id)})
    if session.get('role') == 'admin':
        return redirect(url_for('admin'))
    elif session.get('role') == 'seller':
        return redirect(url_for('seller_dashboard'))
    else:
        return redirect(url_for('home'))

#seller

@app.route('/admin/sellers')
def view_sellers():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    pending_sellers = users_collection.find({'role': 'seller', 'is_approved': False})
    return render_template('pending_sellers.html', sellers=pending_sellers)

# In seller dashboard
@app.route('/seller')
def seller_dashboard():
    if session.get('role') != 'seller':
        return redirect(url_for('login'))
    products = products_collection.find({'owner_email': session['email']})
    return render_template('seller_dashboard.html', products=products)

#approve
@app.route('/approve-seller/<seller_id>')
def approve_seller(seller_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    users_collection.update_one({'_id': ObjectId(seller_id)}, {'$set': {'is_approved': True}})
    return redirect(url_for('admin'))
# cart
@app.route('/add-to-cart/<product_id>')
def add_to_cart(product_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    product = products_collection.find_one({'_id': ObjectId(product_id)})
    if not product:
        return "Product not found!"

    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == str(product['_id']):
            item['quantity'] += 1
            break
    else:
        cart.append({
            'product_id': str(product['_id']),
            'title': product['title'],
            'price': product['price'],
            'image': product['image'],
            'quantity': 1
        })
    session['cart'] = cart
    return redirect(url_for('home'))
#inc and decr
@app.route('/increment/<product_id>')
def increment_item(product_id):
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] += 1
            break
    session['cart'] = cart
    return redirect(url_for('view_cart'))

@app.route('/decrement/<product_id>')
def decrement_item(product_id):
    cart = session.get('cart', [])
    for item in cart:
        if item['product_id'] == product_id:
            item['quantity'] -= 1
            if item['quantity'] <= 0:
                cart = [i for i in cart if i['product_id'] != product_id]
            break
    session['cart'] = cart
    return redirect(url_for('view_cart'))


# view cart
@app.route('/cart')
def view_cart():
    if 'email' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart)
    return render_template('cart.html', cart=cart, total=total)

# remove item from cart
@app.route('/remove-from-cart/<product_id>')
def remove_from_cart(product_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', [])
    cart = [item for item in cart if item['product_id'] != product_id]
    session['cart'] = cart
    return redirect(url_for('view_cart'))


# Logout Route
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

# Start Flask Server
if __name__ == '__main__':
    app.run(debug=True)
