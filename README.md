
# Food Services Application

## Prerequisites

- OpenAI API Key
- MongoDB instance

## Getting Started

### 1. Backend Setup

1. **Environment Variables**
   - In the `back-end` directory, create a `.env` file and add your OpenAI API Key:
     ```plaintext
     OPENAI_API_KEY=your_openai_api_key_here
     ```

2. **Database Setup**
   - Set up a MongoDB database with the following specifications:
     - **Database Name:** `Foodservices`
     - **Collections:** `Fooditems`, `Orders`, `Users`

3. **Run Flask Server**
   - In the `back-end` directory, run the following command to start the Flask server:
     ```bash
     python app.py
     ```

### 2. Frontend Setup

1. **Install Node Modules**
   - Navigate to the `front-end` directory and install required packages by running:
     ```bash
     npm install
     ```

2. **Run Node Server**
   - Go to `front-end/src` and start the Node server with:
     ```bash
     node server.js
     ```

3. **Run the Frontend Application**
   - In the `front-end` directory, start the React application by executing:
     ```bash
     npm start
     ```

## Running the Application

With both the Flask server and Node server running, the application will be accessible, and you can test all features end-to-end.