import os
import time
import gc
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from rembg import remove
from PIL import Image
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this for production

# Configure upload folder (we only need this temporarily)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_remove_file(file_path, max_attempts=5, delay=0.1):
    """
    Safely remove a file with retry logic for Windows file handling issues
    """
    for attempt in range(max_attempts):
        try:
            if os.path.exists(file_path):
                # Force garbage collection to release any file handles
                gc.collect()
                time.sleep(delay)  # Small delay to ensure file handles are released
                os.remove(file_path)
                return True
        except PermissionError:
            if attempt < max_attempts - 1:
                # Increase delay with each attempt
                time.sleep(delay * (attempt + 1))
                continue
            else:
                print(f"Warning: Could not delete {file_path} after {max_attempts} attempts")
                return False
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False
    return True

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Check if filename is empty
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        # Check if file is allowed
        if not allowed_file(file.filename):
            flash('Invalid file type. Allowed types: PNG, JPG, JPEG, WEBP')
            return redirect(request.url)
        
        input_path = None
        input_image = None
        output_image = None
        
        try:
            # Secure filename
            filename = secure_filename(file.filename)
            filename_without_ext = os.path.splitext(filename)[0]
            
            # Save original temporarily
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_path)
            
            # Process image with proper resource management
            with Image.open(input_path) as input_image:
                # Create a copy to avoid file handle issues
                img_copy = input_image.copy()
            
            # Remove background
            output_image = remove(img_copy)
            
            # Create in-memory file
            img_io = BytesIO()
            output_image.save(img_io, 'PNG')
            img_io.seek(0)
            
            # Clean up variables to help with garbage collection
            del img_copy, output_image
            gc.collect()
            
            # Delete temporary file with retry logic
            safe_remove_file(input_path)
            
            # Send directly to browser
            return send_file(
                img_io,
                mimetype='image/png',
                as_attachment=True,
                download_name=f"{filename_without_ext}_no_bg.png"
            )
        
        except Exception as e:
            # Clean up if error occurs
            if input_path and os.path.exists(input_path):
                safe_remove_file(input_path)
            
            # Clean up any remaining variables
            if 'img_copy' in locals():
                del img_copy
            if 'output_image' in locals():
                del output_image
            gc.collect()
            
            flash(f'Error processing image: {str(e)}')
            return redirect(request.url)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)