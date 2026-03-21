"""
PWA Icon Generator for PM Internship Portal
This script creates simple colored icons for the PWA manifest
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_app_icon(size, filename):
    """Create a simple app icon with the specified size"""
    # Create a new image with a blue gradient background
    img = Image.new('RGB', (size, size), color='#3498db')
    draw = ImageDraw.Draw(img)
    
    # Add a circular background
    margin = size // 10
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#2c3e50')
    
    # Add inner circle
    inner_margin = size // 4
    draw.ellipse([inner_margin, inner_margin, size-inner_margin, size-inner_margin], fill='#3498db')
    
    # Add text (PM) in the center
    try:
        # Try to use a font that exists on most systems
        font_size = size // 3
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fall back to default font
        font = ImageFont.load_default()
    
    text = "PM"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    # Save the image
    img.save(filename, 'PNG')
    print(f"Created icon: {filename} ({size}x{size})")

def main():
    """Generate all required icon sizes"""
    icon_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    icons_dir = "static/images/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    for size in icon_sizes:
        filename = f"{icons_dir}/icon-{size}x{size}.png"
        create_app_icon(size, filename)
    
    print("✅ All PWA icons generated successfully!")

if __name__ == "__main__":
    main()