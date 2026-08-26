-- Phase 6.7: Human Handoff & Ticket System (MySQL 8+)
CREATE TABLE IF NOT EXISTS tickets (
    id INT NOT NULL AUTO_INCREMENT,
    ticket_id VARCHAR(32) NOT NULL,
    user_id INT NOT NULL,
    session_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    source VARCHAR(32) NOT NULL DEFAULT 'user_request',
    trace_id VARCHAR(36) NULL,
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tickets_ticket_id (ticket_id),
    KEY ix_tickets_user_id (user_id),
    KEY ix_tickets_session_id (session_id),
    KEY ix_tickets_status (status),
    KEY ix_tickets_priority (priority),
    KEY ix_tickets_trace_id (trace_id),
    KEY ix_tickets_created_time (created_time),
    CONSTRAINT fk_tickets_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_tickets_session FOREIGN KEY (session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ticket_messages (
    id INT NOT NULL AUTO_INCREMENT,
    ticket_id VARCHAR(32) NOT NULL,
    sender_type VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_ticket_messages_ticket_id (ticket_id),
    CONSTRAINT fk_ticket_messages_ticket FOREIGN KEY (ticket_id)
        REFERENCES tickets (ticket_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
