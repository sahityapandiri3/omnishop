# Omnishop - AI Interior Design Platform

A full-stack AI-powered interior design application that helps users transform their spaces with personalized product recommendations and room visualization.

## 🚀 Features

- **AI Design Assistant**: Chat with our AI to get personalized interior design recommendations
- **Product Catalog**: Browse thousands of furniture and decor items from premium brands
- **Smart Search & Filtering**: Find products based on style, price, brand, and availability
- **Room Visualization**: Visualize how products would look in your space
- **Image Analysis**: Upload photos of your room for better recommendations
- **Real-time Chat**: Interactive conversation with design insights and product suggestions

## 🏗️ Architecture

### Frontend (Next.js 14)
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS with custom design system
- **State Management**: React Query for server state
- **UI Components**: Custom components with accessibility features

### Backend (FastAPI)
- **Framework**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **AI Integration**: OpenAI ChatGPT API with vision capabilities
- **Image Processing**: PIL for image optimization
- **API Documentation**: Auto-generated with OpenAPI/Swagger

## 🛠️ Quick Start

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.8+ with pip
- **PostgreSQL** 12+ database
- **OpenAI API Key** for ChatGPT integration

### 1. Clone and Setup

```bash
git clone <repository-url>
cd omnishop
```

### 2. Environment Configuration

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/omnishop

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-vision-preview
```

### 3. Database Setup

Create a PostgreSQL database named `omnishop`.

### 4. One-Command Start

Run both frontend and backend simultaneously:

```bash
./start-all.sh
```

This will:
- Install all dependencies
- Start the backend API on http://localhost:8000
- Start the frontend on http://localhost:3000
- Display API documentation at http://localhost:8000/docs

## 📖 Usage

### 1. Browse Products
- Visit http://localhost:3000/products
- Use search and filters to find items

### 2. Chat with AI Designer
- Go to http://localhost:3000/chat
- Describe your space and style preferences
- Upload room photos for better recommendations

### 3. Visualize Your Space
- Visit http://localhost:3000/visualize
- Chat with AI to get recommendations
- Place products in your room visualization

## 🛡️ Important Notes

- **OpenAI API Key**: You need a valid OpenAI API key for the ChatGPT integration to work
- **Database**: The application will create tables automatically on first run
- **CORS**: Frontend and backend are configured to work together on localhost

## 📁 Key Files

- `prompt.md` - ChatGPT system prompt for interior design analysis
- `spec.md` - Complete technical specifications
- `todo.md` - Development milestones and tasks
- `.env.example` - Environment configuration template

---

**Built with ❤️ using Next.js, FastAPI, and OpenAI**
