import psycopg2
from psycopg2 import sql, extras
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from contextlib import contextmanager


class RelationalDatabaseService:
    """Service for managing relational database operations for users, chat history, and mood tracking."""
    
    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize database connection.
        
        Args:
            db_config: Dictionary containing database configuration
                      (host, database, user, password, port)
        """
        self.db_config = db_config
        self.connection = None
        self.cursor = None
        self._connect()
    
    def _connect(self):
        """Establish database connection."""
        self.connection = psycopg2.connect(**self.db_config)
        self.cursor = self.connection.cursor(cursor_factory=extras.RealDictCursor)
    
    @contextmanager
    def get_cursor(self):
        """Context manager for cursor operations with automatic commit/rollback."""
        try:
            yield self.cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of dictionaries containing query results
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description:  # SELECT query
                return cursor.fetchall()
            return []
    
    def initialize_tables(self):
        """Create all necessary tables if they don't exist."""
        # Create User table
        create_user_table = """
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            user_name VARCHAR(255) NOT NULL,
            user_email VARCHAR(256) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create Chat History table
        create_chat_history_table = """
        CREATE TABLE IF NOT EXISTS chat_history (
            user_id INTEGER NOT NULL,
            time_stamp TIMESTAMP NOT NULL,
            chat_content TEXT NOT NULL,
            PRIMARY KEY (user_id, time_stamp),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """
        
        # Create Mood table
        create_mood_table = """
        CREATE TABLE IF NOT EXISTS mood (
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            average_mood FLOAT NOT NULL CHECK (average_mood >= 0 AND average_mood <= 10),
            PRIMARY KEY (user_id, date),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """
        
        # Create indexes for better query performance
        create_indexes = """
        CREATE INDEX IF NOT EXISTS idx_chat_history_timestamp ON chat_history(time_stamp);
        CREATE INDEX IF NOT EXISTS idx_mood_date ON mood(date);
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(create_user_table)
            cursor.execute(create_chat_history_table)
            cursor.execute(create_mood_table)
            cursor.execute(create_indexes)
    
    # ===== User Operations =====
    
    def create_user(self, user_name: str, user_email: str) -> int:
        """
        Create a new user.
        
        Args:
            user_name: Name of the user
            user_email: Email of the user (must be unique)
            
        Returns:
            user_id of the created user
        """
        query = """
        INSERT INTO users (user_name, user_email)
        VALUES (%s, %s)
        RETURNING user_id;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (user_name, user_email))
            result = cursor.fetchone()
            return result['user_id']
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Get user by ID.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary containing user information or None if not found
        """
        query = "SELECT * FROM users WHERE user_id = %s;"
        results = self.execute_query(query, (user_id,))
        return results[0] if results else None
    
    def get_user_by_email(self, user_email: str) -> Optional[Dict]:
        """
        Get user by email.
        
        Args:
            user_email: Email of the user
            
        Returns:
            Dictionary containing user information or None if not found
        """
        query = "SELECT * FROM users WHERE user_email = %s;"
        results = self.execute_query(query, (user_email,))
        return results[0] if results else None
    
    def update_user(self, user_id: int, user_name: Optional[str] = None, 
                   user_email: Optional[str] = None) -> bool:
        """
        Update user information.
        
        Args:
            user_id: ID of the user
            user_name: New name (optional)
            user_email: New email (optional)
            
        Returns:
            True if update successful, False otherwise
        """
        updates = []
        params = []
        
        if user_name is not None:
            updates.append("user_name = %s")
            params.append(user_name)
        
        if user_email is not None:
            updates.append("user_email = %s")
            params.append(user_email)
        
        if not updates:
            return False
        
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s;"
        
        self.execute_query(query, tuple(params))
        return True
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user and all associated data (cascades to chat_history and mood).
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if deletion successful
        """
        query = "DELETE FROM users WHERE user_id = %s;"
        self.execute_query(query, (user_id,))
        return True
    
    def list_all_users(self) -> List[Dict]:
        """
        Get all users.
        
        Returns:
            List of dictionaries containing all users
        """
        query = "SELECT * FROM users ORDER BY user_id;"
        return self.execute_query(query)
    
    # ===== Chat History Operations =====
    
    def add_chat_history(self, user_id: int, chat_content: str, 
                        time_stamp: Optional[datetime] = None) -> bool:
        """
        Add a chat history entry.
        
        Args:
            user_id: ID of the user
            chat_content: Content of the chat
            time_stamp: Timestamp of the chat (defaults to current time)
            
        Returns:
            True if insertion successful
        """
        if time_stamp is None:
            time_stamp = datetime.now()
        
        query = """
        INSERT INTO chat_history (user_id, time_stamp, chat_content)
        VALUES (%s, %s, %s);
        """
        self.execute_query(query, (user_id, time_stamp, chat_content))
        return True
    
    def get_chat_history_by_user(self, user_id: int, 
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None) -> List[Dict]:
        """
        Get chat history for a user, optionally filtered by date range.
        
        Args:
            user_id: ID of the user
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            List of chat history entries
        """
        query = "SELECT * FROM chat_history WHERE user_id = %s"
        params = [user_id]
        
        if start_date:
            query += " AND time_stamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND time_stamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY time_stamp DESC;"
        
        return self.execute_query(query, tuple(params))
    
    def get_chat_history_by_timestamp(self, user_id: int, 
                                      time_stamp: datetime) -> Optional[Dict]:
        """
        Get a specific chat history entry.
        
        Args:
            user_id: ID of the user
            time_stamp: Timestamp of the chat
            
        Returns:
            Chat history entry or None if not found
        """
        query = """
        SELECT * FROM chat_history 
        WHERE user_id = %s AND time_stamp = %s;
        """
        results = self.execute_query(query, (user_id, time_stamp))
        return results[0] if results else None
    
    def update_chat_history(self, user_id: int, time_stamp: datetime, 
                           chat_content: str) -> bool:
        """
        Update a chat history entry.
        
        Args:
            user_id: ID of the user
            time_stamp: Timestamp of the chat
            chat_content: New content
            
        Returns:
            True if update successful
        """
        query = """
        UPDATE chat_history 
        SET chat_content = %s 
        WHERE user_id = %s AND time_stamp = %s;
        """
        self.execute_query(query, (chat_content, user_id, time_stamp))
        return True
    
    def delete_chat_history(self, user_id: int, time_stamp: datetime) -> bool:
        """
        Delete a specific chat history entry.
        
        Args:
            user_id: ID of the user
            time_stamp: Timestamp of the chat
            
        Returns:
            True if deletion successful
        """
        query = """
        DELETE FROM chat_history 
        WHERE user_id = %s AND time_stamp = %s;
        """
        self.execute_query(query, (user_id, time_stamp))
        return True
    
    # ===== Mood Operations =====
    
    def add_mood(self, user_id: int, average_mood: float, 
                mood_date: Optional[date] = None) -> bool:
        """
        Add a mood entry for a user on a specific date.
        
        Args:
            user_id: ID of the user
            average_mood: Mood value (0-10)
            mood_date: Date of the mood entry (defaults to today)
            
        Returns:
            True if insertion successful
        """
        if mood_date is None:
            mood_date = date.today()
        
        query = """
        INSERT INTO mood (user_id, date, average_mood)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET average_mood = EXCLUDED.average_mood;
        """
        self.execute_query(query, (user_id, mood_date, average_mood))
        return True
    
    def get_mood_by_date(self, user_id: int, mood_date: date) -> Optional[Dict]:
        """
        Get mood entry for a specific date.
        
        Args:
            user_id: ID of the user
            mood_date: Date to query
            
        Returns:
            Mood entry or None if not found
        """
        query = """
        SELECT * FROM mood 
        WHERE user_id = %s AND date = %s;
        """
        results = self.execute_query(query, (user_id, mood_date))
        return results[0] if results else None
    
    def get_mood_history(self, user_id: int, 
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None) -> List[Dict]:
        """
        Get mood history for a user, optionally filtered by date range.
        
        Args:
            user_id: ID of the user
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)
            
        Returns:
            List of mood entries
        """
        query = "SELECT * FROM mood WHERE user_id = %s"
        params = [user_id]
        
        if start_date:
            query += " AND date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= %s"
            params.append(end_date)
        
        query += " ORDER BY date DESC;"
        
        return self.execute_query(query, tuple(params))
    
    def update_mood(self, user_id: int, mood_date: date, 
                   average_mood: float) -> bool:
        """
        Update mood entry for a specific date.
        
        Args:
            user_id: ID of the user
            mood_date: Date of the mood entry
            average_mood: New mood value (0-10)
            
        Returns:
            True if update successful
        """
        query = """
        UPDATE mood 
        SET average_mood = %s 
        WHERE user_id = %s AND date = %s;
        """
        self.execute_query(query, (average_mood, user_id, mood_date))
        return True
    
    def delete_mood(self, user_id: int, mood_date: date) -> bool:
        """
        Delete mood entry for a specific date.
        
        Args:
            user_id: ID of the user
            mood_date: Date of the mood entry
            
        Returns:
            True if deletion successful
        """
        query = "DELETE FROM mood WHERE user_id = %s AND date = %s;"
        self.execute_query(query, (user_id, mood_date))
        return True
    
    def get_average_mood_range(self, user_id: int, 
                              start_date: date, end_date: date) -> Optional[float]:
        """
        Calculate average mood over a date range.
        
        Args:
            user_id: ID of the user
            start_date: Start date
            end_date: End date
            
        Returns:
            Average mood value or None if no data
        """
        query = """
        SELECT AVG(average_mood) as avg_mood 
        FROM mood 
        WHERE user_id = %s AND date BETWEEN %s AND %s;
        """
        results = self.execute_query(query, (user_id, start_date, end_date))
        return results[0]['avg_mood'] if results and results[0]['avg_mood'] else None
    
    # ===== Connection Management =====
    
    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.close()


# Example usage
if __name__ == "__main__":
    # Database configuration
    db_config = {
        'host': 'localhost',
        'database': 'postgres',
        'user': 'postgres',
        'password': '12345678',
        'port': 5432
    }
    
    # Using context manager for automatic cleanup
    with RelationalDatabaseService(db_config) as db:
        # Initialize tables
        db.initialize_tables()
        
        # Create a user
        user_id = db.create_user("John Doe", "john@example.com")
        print(f"Created user with ID: {user_id}")
        
        # Add chat history
        db.add_chat_history(user_id, "Hello, how are you?")
        
        # Add mood
        db.add_mood(user_id, 8.5)
        
        # Get user data
        user = db.get_user_by_id(user_id)
        print(f"User: {user}")
        
        # Get chat history
        chats = db.get_chat_history_by_user(user_id)
        print(f"Chat history: {chats}")
        
        # Get mood
        mood = db.get_mood_by_date(user_id, date.today())
        print(f"Today's mood: {mood}")
