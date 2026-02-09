ALTER TABLE runs
MODIFY COLUMN scale ENUM('mini','small','demo','large') NOT NULL;
