"""
Seed script to populate Product_Images and Banners tables with placeholder images.
Run this script after database initialization to populate images for existing products.
"""
import os
import sys
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import DB_PATH


# Placeholder image URLs for different product categories
PRODUCT_IMAGE_TEMPLATES = {
    "default": [
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&h=800&fit=crop",
    ],
    "kitchen": [
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=800&h=800&fit=crop",
    ],
    "refrigerator": [
        "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1584905066893-7d5c142ba4e1?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1556910103-1c02745a30bf?w=800&h=800&fit=crop",
    ],
    "washing_machine": [
        "https://images.unsplash.com/photo-1626785774573-4b799314346d?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1558317374-a309d3b5c5f5?w=800&h=800&fit=crop",
    ],
    "tv": [
        "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1461151304267-38535e780c79?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1593784991095-a205069470b6?w=800&h=800&fit=crop",
    ],
    "air_conditioner": [
        "https://images.unsplash.com/photo-1585771724684-38269d6639fd?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1567513850573-9e9e13b14a24?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1581622634859-529b8dfac9f5?w=800&h=800&fit=crop",
    ],
    "microwave": [
        "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1584905066893-7d5c142ba4e1?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&h=800&fit=crop",
    ],
    "blender": [
        "https://images.unsplash.com/photo-1570222094114-d054a817e56b?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1570222094194-0fe85b2c7942?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&h=800&fit=crop",
    ],
    "coffee_maker": [
        "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=800&h=800&fit=crop",
    ],
    "vacuum": [
        "https://images.unsplash.com/photo-1558317374-a309d3b5c5f5?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=800&h=800&fit=crop",
        "https://images.unsplash.com/photo-1558317374-a309d3b5c5f5?w=800&h=800&fit=crop",
    ],
}

# Banner images for homepage slider
BANNER_DATA = [
    {
        "TieuDe": "Mega Sale - Giảm đến 50%",
        "MoTa": "Khuyến mãi đặc biệt cho toàn bộ sản phẩm đồ gia dụng",
        "URL": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1920&h=600&fit=crop",
        "Link": "/san-pham",
        "ThuTu": 1,
    },
    {
        "TieuDe": "Bộ sưu tập Tủ lạnh mới",
        "MoTa": "Công nghệ inverter, tiết kiệm điện năng tối đa",
        "URL": "https://images.unsplash.com/photo-1571175443880-49e1d25b2bc5?w=1920&h=600&fit=crop",
        "Link": "/san-pham",
        "ThuTu": 2,
    },
    {
        "TieuDe": "Máy giặt thông minh",
        "MoTa": "Công nghệ AI, bảo vệ quần áo tối ưu",
        "URL": "https://images.unsplash.com/photo-1626785774573-4b799314346d?w=1920&h=600&fit=crop",
        "Link": "/san-pham",
        "ThuTu": 3,
    },
    {
        "TieuDe": "TV 4K Ultra HD",
        "MoTa": "Trải nghiệm giải trí đỉnh cao ngay tại nhà",
        "URL": "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=1920&h=600&fit=crop",
        "Link": "/san-pham",
        "ThuTu": 4,
    },
]


def get_product_category(product_name):
    """Determine product category based on product name."""
    name_lower = product_name.lower()
    
    category_keywords = {
        "refrigerator": ["tủ lạnh", "tủ lạnh", "fridge", "refrigerator"],
        "washing_machine": ["máy giặt", "washing machine", "washer"],
        "tv": ["tv", "television", "tivi", "máy chiếu"],
        "air_conditioner": ["điều hòa", "air conditioner", "ac"],
        "microwave": ["lò vi sóng", "microwave"],
        "blender": ["máy xay", "blender"],
        "coffee_maker": ["máy pha cà phê", "coffee maker", "coffee"],
        "vacuum": ["máy hút bụi", "vacuum"],
        "kitchen": ["bếp", "kitchen", "nồi", "chảo"],
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
    
    return "default"


def seed_product_images(conn):
    """Seed product images for all existing products."""
    print("Seeding product images...")
    
    # Get all products
    products = conn.execute("SELECT MaSanPham, TenSanPham FROM SanPham").fetchall()
    
    if not products:
        print("No products found in database.")
        return
    
    # Check if images already exist
    existing_images = conn.execute("SELECT COUNT(*) FROM Product_Images").fetchone()[0]
    if existing_images > 0:
        print(f"Product images already exist ({existing_images} records). Skipping...")
        return
    
    for product in products:
        product_id = product[0]
        product_name = product[1]
        
        # Determine category
        category = get_product_category(product_name)
        image_urls = PRODUCT_IMAGE_TEMPLATES.get(category, PRODUCT_IMAGE_TEMPLATES["default"])
        
        # Insert images (first one as primary)
        for idx, url in enumerate(image_urls):
            is_primary = 1 if idx == 0 else 0
            conn.execute(
                """INSERT INTO Product_Images (MaSanPham, URL, LaChinh, ThuTu)
                   VALUES (?, ?, ?, ?)""",
                (product_id, url, is_primary, idx)
            )
        
        print(f"  - Added {len(image_urls)} images for product: {product_name}")
    
    conn.commit()
    print(f"✓ Seeded images for {len(products)} products")


def seed_banners(conn):
    """Seed promotional banners for homepage slider."""
    print("Seeding banners...")
    
    # Check if banners already exist
    existing_banners = conn.execute("SELECT COUNT(*) FROM Banners").fetchone()[0]
    if existing_banners > 0:
        print(f"Banners already exist ({existing_banners} records). Skipping...")
        return
    
    for banner in BANNER_DATA:
        conn.execute(
            """INSERT INTO Banners (TieuDe, MoTa, URL, Link, TrangThai, ThuTu)
               VALUES (?, ?, ?, ?, 'hoat_dong', ?)""",
            (banner["TieuDe"], banner["MoTa"], banner["URL"], banner["Link"], banner["ThuTu"])
        )
        print(f"  - Added banner: {banner['TieuDe']}")
    
    conn.commit()
    print(f"✓ Seeded {len(BANNER_DATA)} banners")


def main():
    """Main function to run the seed script."""
    print("=" * 60)
    print("Image Seeding Script")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        print("Please run the application first to initialize the database.")
        sys.exit(1)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Seed product images
        seed_product_images(conn)
        
        # Seed banners
        seed_banners(conn)
        
        print("\n" + "=" * 60)
        print("✓ Image seeding completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during seeding: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
