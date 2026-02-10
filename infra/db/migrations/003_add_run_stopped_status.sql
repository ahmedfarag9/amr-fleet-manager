ALTER TABLE runs
MODIFY COLUMN status ENUM('started','completed','failed','stopped') NOT NULL DEFAULT 'started';
