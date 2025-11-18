"""
Data quality validation and cleaning utilities
"""
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from api.database.connection import get_db_session
from api.database.models import Product, ProductImage, Category, ScrapingLog

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """Validate and clean scraped product data"""

    def __init__(self):
        self.validation_rules = {
            'name': self._validate_name,
            'price': self._validate_price,
            'description': self._validate_description,
            'images': self._validate_images,
            'category': self._validate_category,
            'brand': self._validate_brand,
        }

    def validate_product(self, product_data: Dict) -> Tuple[bool, List[str]]:
        """Validate product data and return (is_valid, errors)"""
        errors = []

        for field, validator in self.validation_rules.items():
            if field in product_data:
                is_valid, error_msg = validator(product_data[field])
                if not is_valid:
                    errors.append(f"{field}: {error_msg}")

        return len(errors) == 0, errors

    def _validate_name(self, name: str) -> Tuple[bool, Optional[str]]:
        """Validate product name"""
        if not name or len(name.strip()) < 3:
            return False, "Name must be at least 3 characters long"

        if len(name) > 500:
            return False, "Name exceeds maximum length of 500 characters"

        # Check for placeholder text
        placeholder_patterns = [
            r'test\s*product',
            r'sample\s*item',
            r'lorem\s*ipsum',
            r'placeholder',
            r'temp\s*name'
        ]

        for pattern in placeholder_patterns:
            if re.search(pattern, name.lower()):
                return False, "Name appears to be placeholder text"

        return True, None

    def _validate_price(self, price: float) -> Tuple[bool, Optional[str]]:
        """Validate product price"""
        if price is None:
            return False, "Price is required"

        if price <= 0:
            return False, "Price must be greater than 0"

        if price > 1000000:
            return False, "Price exceeds reasonable maximum (1,000,000)"

        return True, None

    def _validate_description(self, description: str) -> Tuple[bool, Optional[str]]:
        """Validate product description"""
        if not description:
            return True, None  # Description is optional

        if len(description) < 10:
            return False, "Description too short (minimum 10 characters)"

        if len(description) > 5000:
            return False, "Description exceeds maximum length"

        # Check for placeholder text
        if re.search(r'lorem\s*ipsum|placeholder|test\s*description', description.lower()):
            return False, "Description appears to be placeholder text"

        return True, None

    def _validate_images(self, images: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate product images"""
        if not images:
            return False, "At least one image is required"

        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        invalid_images = []

        for img_url in images:
            if not any(img_url.lower().endswith(ext) for ext in valid_extensions):
                invalid_images.append(img_url)

        if invalid_images:
            return False, f"Invalid image formats: {', '.join(invalid_images[:3])}"

        return True, None

    def _validate_category(self, category: str) -> Tuple[bool, Optional[str]]:
        """Validate product category"""
        if not category:
            return True, None  # Category is optional

        if len(category) > 100:
            return False, "Category name too long"

        return True, None

    def _validate_brand(self, brand: str) -> Tuple[bool, Optional[str]]:
        """Validate product brand"""
        if not brand:
            return True, None  # Brand is optional

        if len(brand) > 100:
            return False, "Brand name too long"

        return True, None


class DuplicateDetector:
    """Detect and handle duplicate products"""

    def __init__(self):
        self.similarity_threshold = 0.85

    def find_duplicates(self) -> List[Dict]:
        """Find potential duplicate products in database"""
        duplicates = []

        with get_db_session() as session:
            products = session.query(Product).all()

            # Group products by similarity
            for i, product1 in enumerate(products):
                for product2 in products[i+1:]:
                    similarity = self._calculate_similarity(product1, product2)
                    if similarity >= self.similarity_threshold:
                        duplicates.append({
                            'product1_id': product1.id,
                            'product2_id': product2.id,
                            'similarity': similarity,
                            'reason': self._get_similarity_reason(product1, product2)
                        })

        return duplicates

    def _calculate_similarity(self, product1: Product, product2: Product) -> float:
        """Calculate similarity score between two products"""
        scores = []

        # Name similarity
        name_sim = self._text_similarity(product1.name, product2.name)
        scores.append(name_sim * 0.4)  # 40% weight

        # Price similarity (within 5%)
        if product1.price and product2.price:
            price_diff = abs(product1.price - product2.price) / max(product1.price, product2.price)
            price_sim = max(0, 1 - price_diff * 20)  # 5% diff = 0 similarity
            scores.append(price_sim * 0.3)  # 30% weight

        # Brand similarity
        if product1.brand and product2.brand:
            brand_sim = 1.0 if product1.brand.lower() == product2.brand.lower() else 0.0
            scores.append(brand_sim * 0.2)  # 20% weight

        # Source website penalty (same source more likely to be duplicate)
        source_penalty = 0.1 if product1.source_website == product2.source_website else 0.0
        scores.append(source_penalty * 0.1)  # 10% weight

        return sum(scores) / len(scores) if scores else 0.0

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple word overlap"""
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _get_similarity_reason(self, product1: Product, product2: Product) -> str:
        """Get human-readable reason for similarity"""
        reasons = []

        name_sim = self._text_similarity(product1.name, product2.name)
        if name_sim > 0.8:
            reasons.append("Similar names")

        if product1.brand and product2.brand and product1.brand.lower() == product2.brand.lower():
            reasons.append("Same brand")

        if product1.price and product2.price:
            price_diff = abs(product1.price - product2.price) / max(product1.price, product2.price)
            if price_diff < 0.05:
                reasons.append("Similar prices")

        if product1.source_website == product2.source_website:
            reasons.append("Same source")

        return ", ".join(reasons) if reasons else "General similarity"


class DataCleaner:
    """Clean and normalize product data"""

    def clean_all_products(self):
        """Clean all products in database"""
        with get_db_session() as session:
            products = session.query(Product).all()

            for product in products:
                self._clean_product(product, session)

            session.commit()
            logger.info(f"Cleaned {len(products)} products")

    def _clean_product(self, product: Product, session: Session):
        """Clean individual product"""
        # Clean name
        if product.name:
            product.name = self._clean_text(product.name)

        # Clean description
        if product.description:
            product.description = self._clean_text(product.description)

        # Normalize brand
        if product.brand:
            product.brand = self._normalize_brand(product.brand)

        # Validate and clean price
        if product.price:
            product.price = round(product.price, 2)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return text

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove special characters that might cause issues
        text = re.sub(r'[^\w\s\-.,()/$%&]', '', text)

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")

        return text

    def _normalize_brand(self, brand: str) -> str:
        """Normalize brand names"""
        if not brand:
            return brand

        # Convert to title case
        brand = brand.strip().title()

        # Handle common brand variations
        brand_mappings = {
            'West Elm': 'West Elm',
            'Westelm': 'West Elm',
            'Orange Tree': 'Orange Tree',
            'Orangetree': 'Orange Tree',
            'Pelican Essentials': 'Pelican Essentials',
            'PelicanEssentials': 'Pelican Essentials'
        }

        return brand_mappings.get(brand, brand)


class QualityReporter:
    """Generate data quality reports"""

    def generate_quality_report(self) -> Dict:
        """Generate comprehensive data quality report"""
        with get_db_session() as session:
            # Basic statistics
            total_products = session.query(Product).count()
            products_with_images = session.query(Product).join(ProductImage).distinct().count()
            products_with_description = session.query(Product).filter(Product.description.isnot(None)).count()
            products_available = session.query(Product).filter(Product.is_available == True).count()

            # Source website breakdown
            source_stats = {}
            for website in ['westelm', 'orangetree', 'pelicanessentials']:
                count = session.query(Product).filter(Product.source_website == website).count()
                source_stats[website] = count

            # Category breakdown
            category_stats = {}
            categories = session.query(Category).all()
            for category in categories:
                count = session.query(Product).filter(Product.category_id == category.id).count()
                if count > 0:
                    category_stats[category.name] = count

            # Price statistics
            prices = [p.price for p in session.query(Product.price).filter(Product.price.isnot(None)).all()]
            price_stats = {}
            if prices:
                price_stats = {
                    'min': min(prices),
                    'max': max(prices),
                    'average': sum(prices) / len(prices),
                    'count': len(prices)
                }

            # Data quality metrics
            validator = DataQualityValidator()
            quality_issues = 0
            sample_products = session.query(Product).limit(100).all()

            for product in sample_products:
                product_data = {
                    'name': product.name,
                    'price': product.price,
                    'description': product.description,
                    'brand': product.brand,
                }
                is_valid, errors = validator.validate_product(product_data)
                if not is_valid:
                    quality_issues += 1

            quality_score = (len(sample_products) - quality_issues) / len(sample_products) * 100 if sample_products else 0

            return {
                'total_products': total_products,
                'products_with_images': products_with_images,
                'products_with_description': products_with_description,
                'products_available': products_available,
                'image_coverage': (products_with_images / total_products * 100) if total_products > 0 else 0,
                'description_coverage': (products_with_description / total_products * 100) if total_products > 0 else 0,
                'availability_rate': (products_available / total_products * 100) if total_products > 0 else 0,
                'source_breakdown': source_stats,
                'category_breakdown': category_stats,
                'price_statistics': price_stats,
                'quality_score': quality_score,
                'generated_at': datetime.utcnow().isoformat()
            }

    def log_quality_issues(self) -> List[Dict]:
        """Log and return quality issues found"""
        issues = []
        validator = DataQualityValidator()

        with get_db_session() as session:
            products = session.query(Product).all()

            for product in products:
                product_data = {
                    'name': product.name,
                    'price': product.price,
                    'description': product.description,
                    'brand': product.brand,
                }

                is_valid, errors = validator.validate_product(product_data)
                if not is_valid:
                    issues.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'source_url': product.source_url,
                        'errors': errors
                    })

        logger.info(f"Found {len(issues)} quality issues")
        return issues