-- MySQL 8 schema for the grievance case store (generated from grievance_agent/store.py).
-- The app also creates these tables automatically on first start.
CREATE DATABASE IF NOT EXISTS grievance CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE grievance;

CREATE TABLE audit_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(32), 
	actor VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	detail JSON NOT NULL, 
	at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_audit_log_case_id ON audit_log (case_id);

CREATE TABLE cases (
	id VARCHAR(32) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	student_ref VARCHAR(64), 
	route VARCHAR(32), 
	urgency_level VARCHAR(16) NOT NULL, 
	urgency_score FLOAT NOT NULL, 
	category VARCHAR(32), 
	reviewer_outcome VARCHAR(96), 
	reviewer_notes TEXT, 
	closed_at DATETIME, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_cases_created_at ON cases (created_at);

CREATE INDEX ix_cases_route ON cases (route);

CREATE INDEX ix_cases_status ON cases (status);

CREATE TABLE consent_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(32) NOT NULL, 
	event VARCHAR(32) NOT NULL, 
	notice_version VARCHAR(16) NOT NULL, 
	at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_consent_log_case_id ON consent_log (case_id);

CREATE TABLE precedents (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	text_redacted TEXT NOT NULL, 
	label VARCHAR(16) NOT NULL, 
	embedding BLOB NOT NULL, 
	embed_model VARCHAR(128) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE rubric_ratings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	run_id VARCHAR(64) NOT NULL, 
	item_id VARCHAR(32) NOT NULL, 
	rater VARCHAR(64) NOT NULL, 
	scores JSON NOT NULL, 
	comment TEXT, 
	at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_rubric_ratings_run_id ON rubric_ratings (run_id);

CREATE INDEX ix_rubric_ratings_item_id ON rubric_ratings (item_id);

CREATE TABLE escalations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(32) NOT NULL, 
	route VARCHAR(32) NOT NULL, 
	reasons JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	acknowledged_by VARCHAR(64), 
	acknowledged_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_escalations_case_id ON escalations (case_id);

CREATE TABLE records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	record_json JSON NOT NULL, 
	verification_json JSON NOT NULL, 
	created_by VARCHAR(32) NOT NULL, 
	student_confirmed BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_records_case_id ON records (case_id);

CREATE TABLE turns (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	case_id VARCHAR(32) NOT NULL, 
	idx INTEGER NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	text_redacted TEXT NOT NULL, 
	meta JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX ix_turns_case_id ON turns (case_id);
