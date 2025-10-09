"""
Machine Learning models for advanced product recommendations
"""
import logging
import numpy as np
import asyncio
from typing import Dict, List, Optional, Any, Tuple
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
import pickle
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """User profile for personalization"""
    user_id: str
    style_preferences: List[str]
    color_preferences: List[str]
    material_preferences: List[str]
    budget_range: Tuple[float, float]
    room_types: List[str]
    interaction_history: List[Dict[str, Any]]
    purchase_history: List[Dict[str, Any]]
    preference_confidence: float
    last_updated: datetime


@dataclass
class ProductEmbedding:
    """Product feature embedding"""
    product_id: str
    style_vector: np.ndarray
    color_vector: np.ndarray
    material_vector: np.ndarray
    functional_vector: np.ndarray
    price_vector: np.ndarray
    description_vector: np.ndarray
    combined_embedding: np.ndarray


class ContentBasedMLModel:
    """Content-based machine learning model for recommendations"""

    def __init__(self):
        self.style_encoder = {}
        self.color_encoder = {}
        self.material_encoder = {}
        self.function_encoder = {}
        self.embeddings_cache = {}
        self.model_cache_path = Path("./data/ml_models")
        self.model_cache_path.mkdir(parents=True, exist_ok=True)

        self._initialize_encoders()
        logger.info("Content-based ML model initialized")

    def _initialize_encoders(self):
        """Initialize feature encoders"""
        # Style encoding
        self.style_encoder = {
            'modern': 0, 'contemporary': 1, 'traditional': 2, 'rustic': 3,
            'scandinavian': 4, 'industrial': 5, 'bohemian': 6, 'mid_century': 7,
            'art_deco': 8, 'mediterranean': 9, 'transitional': 10, 'minimalist': 11
        }

        # Color encoding
        self.color_encoder = {
            'white': 0, 'black': 1, 'gray': 2, 'brown': 3, 'beige': 4,
            'red': 5, 'blue': 6, 'green': 7, 'yellow': 8, 'orange': 9,
            'purple': 10, 'pink': 11, 'gold': 12, 'silver': 13
        }

        # Material encoding
        self.material_encoder = {
            'wood': 0, 'metal': 1, 'fabric': 2, 'leather': 3, 'glass': 4,
            'plastic': 5, 'ceramic': 6, 'stone': 7, 'concrete': 8, 'rattan': 9
        }

        # Function encoding
        self.function_encoder = {
            'seating': 0, 'storage': 1, 'lighting': 2, 'dining': 3,
            'sleeping': 4, 'workspace': 5, 'decoration': 6, 'entertainment': 7
        }

    def create_product_embedding(self, product_data: Dict[str, Any]) -> ProductEmbedding:
        """Create feature embedding for a product"""
        try:
            # Extract features
            style = product_data.get('style', 'contemporary')
            colors = product_data.get('colors', ['neutral'])
            materials = product_data.get('materials', ['unknown'])
            functions = product_data.get('functions', ['decoration'])
            price = product_data.get('price', 0.0)
            description = product_data.get('description', '')

            # Create style vector
            style_vector = np.zeros(len(self.style_encoder))
            if style in self.style_encoder:
                style_vector[self.style_encoder[style]] = 1.0

            # Create color vector
            color_vector = np.zeros(len(self.color_encoder))
            for color in colors:
                if color in self.color_encoder:
                    color_vector[self.color_encoder[color]] = 1.0 / len(colors)

            # Create material vector
            material_vector = np.zeros(len(self.material_encoder))
            for material in materials:
                if material in self.material_encoder:
                    material_vector[self.material_encoder[material]] = 1.0 / len(materials)

            # Create functional vector
            functional_vector = np.zeros(len(self.function_encoder))
            for function in functions:
                if function in self.function_encoder:
                    functional_vector[self.function_encoder[function]] = 1.0 / len(functions)

            # Create price vector (normalized)
            price_vector = np.array([
                min(price / 10000, 1.0),  # Normalized price
                1.0 if price < 500 else 0.0,  # Budget category
                1.0 if 500 <= price < 2000 else 0.0,  # Mid-range
                1.0 if 2000 <= price < 5000 else 0.0,  # Premium
                1.0 if price >= 5000 else 0.0  # Luxury
            ])

            # Create description vector (simple TF-IDF simulation)
            description_vector = self._create_description_vector(description)

            # Combine all vectors
            combined_embedding = np.concatenate([
                style_vector * 0.2,
                color_vector * 0.15,
                material_vector * 0.15,
                functional_vector * 0.25,
                price_vector * 0.1,
                description_vector * 0.15
            ])

            return ProductEmbedding(
                product_id=product_data.get('id', ''),
                style_vector=style_vector,
                color_vector=color_vector,
                material_vector=material_vector,
                functional_vector=functional_vector,
                price_vector=price_vector,
                description_vector=description_vector,
                combined_embedding=combined_embedding
            )

        except Exception as e:
            logger.error(f"Error creating product embedding: {e}")
            # Return default embedding
            default_size = sum([
                len(self.style_encoder),
                len(self.color_encoder),
                len(self.material_encoder),
                len(self.function_encoder),
                5,  # price vector size
                50  # description vector size
            ])
            return ProductEmbedding(
                product_id=product_data.get('id', ''),
                style_vector=np.zeros(len(self.style_encoder)),
                color_vector=np.zeros(len(self.color_encoder)),
                material_vector=np.zeros(len(self.material_encoder)),
                functional_vector=np.zeros(len(self.function_encoder)),
                price_vector=np.zeros(5),
                description_vector=np.zeros(50),
                combined_embedding=np.zeros(default_size)
            )

    def _create_description_vector(self, description: str, vector_size: int = 50) -> np.ndarray:
        """Create simple description vector using keyword frequency"""
        # Simple keyword-based vector (in production, use proper embeddings)
        design_keywords = [
            'modern', 'contemporary', 'classic', 'elegant', 'stylish', 'comfortable',
            'durable', 'sleek', 'versatile', 'functional', 'beautiful', 'luxury',
            'affordable', 'spacious', 'compact', 'practical', 'decorative', 'ornate',
            'minimalist', 'bold', 'subtle', 'warm', 'cool', 'neutral', 'vibrant',
            'soft', 'hard', 'smooth', 'textured', 'glossy', 'matte', 'natural',
            'synthetic', 'handcrafted', 'manufactured', 'vintage', 'new', 'trendy',
            'timeless', 'seasonal', 'indoor', 'outdoor', 'portable', 'fixed',
            'adjustable', 'stackable', 'foldable', 'modular', 'assembled', 'simple'
        ]

        vector = np.zeros(vector_size)
        if description:
            description_lower = description.lower()
            for i, keyword in enumerate(design_keywords[:vector_size]):
                if keyword in description_lower:
                    vector[i] = description_lower.count(keyword)

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    def calculate_similarity(self, embedding1: ProductEmbedding, embedding2: ProductEmbedding) -> float:
        """Calculate cosine similarity between two product embeddings"""
        try:
            # Cosine similarity
            dot_product = np.dot(embedding1.combined_embedding, embedding2.combined_embedding)
            norm1 = np.linalg.norm(embedding1.combined_embedding)
            norm2 = np.linalg.norm(embedding2.combined_embedding)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return max(0.0, similarity)  # Ensure non-negative

        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def find_similar_products(
        self,
        target_embedding: ProductEmbedding,
        product_embeddings: List[ProductEmbedding],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """Find most similar products to target"""
        similarities = []

        for embedding in product_embeddings:
            if embedding.product_id != target_embedding.product_id:
                similarity = self.calculate_similarity(target_embedding, embedding)
                similarities.append((embedding.product_id, similarity))

        # Sort by similarity and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]


class CollaborativeFilteringModel:
    """Collaborative filtering model for user-based recommendations"""

    def __init__(self):
        self.user_item_matrix = {}
        self.item_item_similarity = {}
        self.user_user_similarity = {}
        self.global_average = 0.0
        self.min_interactions = 5

        logger.info("Collaborative filtering model initialized")

    def build_user_item_matrix(self, interactions: List[Dict[str, Any]]):
        """Build user-item interaction matrix"""
        self.user_item_matrix = defaultdict(dict)

        for interaction in interactions:
            user_id = interaction.get('user_id')
            product_id = interaction.get('product_id')
            rating = interaction.get('rating', 1.0)  # Default implicit rating

            if user_id and product_id:
                self.user_item_matrix[user_id][product_id] = rating

        # Calculate global average
        all_ratings = [
            rating for user_ratings in self.user_item_matrix.values()
            for rating in user_ratings.values()
        ]
        self.global_average = sum(all_ratings) / len(all_ratings) if all_ratings else 0.0

        logger.info(f"Built user-item matrix with {len(self.user_item_matrix)} users")

    def calculate_user_similarity(self, user1_id: str, user2_id: str) -> float:
        """Calculate similarity between two users"""
        user1_ratings = self.user_item_matrix.get(user1_id, {})
        user2_ratings = self.user_item_matrix.get(user2_id, {})

        # Find common items
        common_items = set(user1_ratings.keys()) & set(user2_ratings.keys())

        if len(common_items) < 2:
            return 0.0

        # Calculate Pearson correlation
        sum1 = sum(user1_ratings[item] for item in common_items)
        sum2 = sum(user2_ratings[item] for item in common_items)

        sum1_sq = sum(user1_ratings[item] ** 2 for item in common_items)
        sum2_sq = sum(user2_ratings[item] ** 2 for item in common_items)

        sum_products = sum(user1_ratings[item] * user2_ratings[item] for item in common_items)

        n = len(common_items)
        numerator = sum_products - (sum1 * sum2 / n)
        denominator = np.sqrt((sum1_sq - sum1 ** 2 / n) * (sum2_sq - sum2 ** 2 / n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def get_user_recommendations(self, user_id: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Get recommendations for a user using collaborative filtering"""
        if user_id not in self.user_item_matrix:
            return []

        user_ratings = self.user_item_matrix[user_id]

        # Find similar users
        user_similarities = []
        for other_user in self.user_item_matrix:
            if other_user != user_id:
                similarity = self.calculate_user_similarity(user_id, other_user)
                if similarity > 0:
                    user_similarities.append((other_user, similarity))

        user_similarities.sort(key=lambda x: x[1], reverse=True)

        # Get recommendations from similar users
        recommendations = defaultdict(float)
        similarity_sums = defaultdict(float)

        for similar_user, similarity in user_similarities[:50]:  # Top 50 similar users
            similar_user_ratings = self.user_item_matrix[similar_user]

            for product_id, rating in similar_user_ratings.items():
                if product_id not in user_ratings:  # Only recommend unseen items
                    recommendations[product_id] += similarity * rating
                    similarity_sums[product_id] += similarity

        # Normalize recommendations
        final_recommendations = []
        for product_id, weighted_sum in recommendations.items():
            if similarity_sums[product_id] > 0:
                predicted_rating = weighted_sum / similarity_sums[product_id]
                final_recommendations.append((product_id, predicted_rating))

        final_recommendations.sort(key=lambda x: x[1], reverse=True)
        return final_recommendations[:top_k]


class HybridRecommendationModel:
    """Hybrid model combining content-based and collaborative filtering"""

    def __init__(self):
        self.content_model = ContentBasedMLModel()
        self.collaborative_model = CollaborativeFilteringModel()
        self.user_profiles = {}
        self.model_weights = {
            'content': 0.6,
            'collaborative': 0.4
        }

        logger.info("Hybrid recommendation model initialized")

    def create_user_profile(self, user_id: str, user_data: Dict[str, Any]) -> UserProfile:
        """Create or update user profile"""
        return UserProfile(
            user_id=user_id,
            style_preferences=user_data.get('style_preferences', []),
            color_preferences=user_data.get('color_preferences', []),
            material_preferences=user_data.get('material_preferences', []),
            budget_range=user_data.get('budget_range', (0, 10000)),
            room_types=user_data.get('room_types', []),
            interaction_history=user_data.get('interaction_history', []),
            purchase_history=user_data.get('purchase_history', []),
            preference_confidence=user_data.get('preference_confidence', 0.5),
            last_updated=datetime.now()
        )

    def get_hybrid_recommendations(
        self,
        user_id: str,
        candidate_products: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Get hybrid recommendations combining multiple approaches"""

        try:
            # Get content-based recommendations
            content_scores = self._get_content_based_scores(user_id, candidate_products, user_context)

            # Get collaborative filtering recommendations
            collaborative_scores = self._get_collaborative_scores(user_id, candidate_products)

            # Combine scores
            hybrid_scores = []
            for product_data in candidate_products:
                product_id = product_data.get('id')
                content_score = content_scores.get(product_id, 0.0)
                collaborative_score = collaborative_scores.get(product_id, 0.0)

                # Weighted combination
                hybrid_score = (
                    content_score * self.model_weights['content'] +
                    collaborative_score * self.model_weights['collaborative']
                )

                # Add explanation
                explanation = {
                    'content_score': content_score,
                    'collaborative_score': collaborative_score,
                    'hybrid_score': hybrid_score,
                    'primary_reason': 'content' if content_score > collaborative_score else 'collaborative'
                }

                hybrid_scores.append((product_id, hybrid_score, explanation))

            # Sort and return top-k
            hybrid_scores.sort(key=lambda x: x[1], reverse=True)
            return hybrid_scores[:top_k]

        except Exception as e:
            logger.error(f"Error in hybrid recommendations: {e}")
            return []

    def _get_content_based_scores(
        self,
        user_id: str,
        candidate_products: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Get content-based scores for products"""
        scores = {}

        # Create user preference embedding
        user_profile = self.user_profiles.get(user_id)
        if not user_profile and user_context:
            user_profile = self.create_user_profile(user_id, user_context)

        if not user_profile:
            return {product['id']: 0.5 for product in candidate_products}

        # Create user preference "product" for comparison
        user_preferences_data = {
            'id': 'user_preferences',
            'style': user_profile.style_preferences[0] if user_profile.style_preferences else 'modern',
            'colors': user_profile.color_preferences,
            'materials': user_profile.material_preferences,
            'functions': ['decoration'],  # Default
            'price': sum(user_profile.budget_range) / 2,
            'description': ' '.join(user_profile.style_preferences + user_profile.color_preferences)
        }

        user_embedding = self.content_model.create_product_embedding(user_preferences_data)

        # Score each candidate product
        for product_data in candidate_products:
            product_embedding = self.content_model.create_product_embedding(product_data)
            similarity = self.content_model.calculate_similarity(user_embedding, product_embedding)
            scores[product_data['id']] = similarity

        return scores

    def _get_collaborative_scores(self, user_id: str, candidate_products: List[Dict[str, Any]]) -> Dict[str, float]:
        """Get collaborative filtering scores for products"""
        collaborative_recs = self.collaborative_model.get_user_recommendations(user_id, top_k=100)

        # Convert to dictionary for lookup
        collaborative_dict = dict(collaborative_recs)

        scores = {}
        for product_data in candidate_products:
            product_id = product_data['id']
            scores[product_id] = collaborative_dict.get(product_id, 0.0)

        return scores

    def update_user_interaction(self, user_id: str, product_id: str, interaction_type: str, rating: float = 1.0):
        """Update user interaction for model learning"""
        # Update collaborative model
        if user_id not in self.collaborative_model.user_item_matrix:
            self.collaborative_model.user_item_matrix[user_id] = {}

        self.collaborative_model.user_item_matrix[user_id][product_id] = rating

        # Update user profile
        if user_id in self.user_profiles:
            interaction = {
                'product_id': product_id,
                'interaction_type': interaction_type,
                'rating': rating,
                'timestamp': datetime.now().isoformat()
            }
            self.user_profiles[user_id].interaction_history.append(interaction)

    def save_models(self):
        """Save trained models to disk"""
        try:
            # Save collaborative model
            with open(self.content_model.model_cache_path / 'collaborative_model.pkl', 'wb') as f:
                pickle.dump(self.collaborative_model, f)

            # Save user profiles
            with open(self.content_model.model_cache_path / 'user_profiles.pkl', 'wb') as f:
                pickle.dump(self.user_profiles, f)

            logger.info("Models saved successfully")

        except Exception as e:
            logger.error(f"Error saving models: {e}")

    def load_models(self):
        """Load trained models from disk"""
        try:
            # Load collaborative model
            collab_path = self.content_model.model_cache_path / 'collaborative_model.pkl'
            if collab_path.exists():
                with open(collab_path, 'rb') as f:
                    self.collaborative_model = pickle.load(f)

            # Load user profiles
            profiles_path = self.content_model.model_cache_path / 'user_profiles.pkl'
            if profiles_path.exists():
                with open(profiles_path, 'rb') as f:
                    self.user_profiles = pickle.load(f)

            logger.info("Models loaded successfully")

        except Exception as e:
            logger.error(f"Error loading models: {e}")


# Global ML model instance
ml_recommendation_model = HybridRecommendationModel()