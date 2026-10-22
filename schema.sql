-- Blood/Organ Donor-Recipient Matching Registry : schema
-- Run once:  psql -U postgres -d donor_registry -f schema.sql

DROP TABLE IF EXISTS matches, compatibility_rules, recipients, donors, users CASCADE;

-- 1. Users (common table for donors, recipients, hospital staff)
CREATE TABLE users (
    id    SERIAL PRIMARY KEY,
    name  VARCHAR(100) NOT NULL,
    role  VARCHAR(20)  NOT NULL CHECK (role IN ('donor', 'recipient', 'hospital')),
    phone VARCHAR(15),
    email VARCHAR(100)
);

-- 2. Donors
CREATE TABLE donors (
    id         SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blood_type VARCHAR(3) NOT NULL CHECK (blood_type IN ('O-','O+','A-','A+','B-','B+','AB-','AB+')),
    organ_type VARCHAR(30) NOT NULL DEFAULT 'blood'
               CHECK (organ_type IN ('blood','kidney','liver','bone marrow')),
    latitude   DOUBLE PRECISION NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude  DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    status     VARCHAR(20) NOT NULL DEFAULT 'available'
               CHECK (status IN ('available', 'locked', 'donated'))
);

-- 3. Recipients
CREATE TABLE recipients (
    id                SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blood_type_needed VARCHAR(3) NOT NULL CHECK (blood_type_needed IN ('O-','O+','A-','A+','B-','B+','AB-','AB+')),
    organ_needed      VARCHAR(30) NOT NULL DEFAULT 'blood'
                      CHECK (organ_needed IN ('blood','kidney','liver','bone marrow')),
    latitude          DOUBLE PRECISION NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude         DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    urgency           VARCHAR(10) NOT NULL DEFAULT 'normal' CHECK (urgency IN ('critical', 'high', 'normal')),
    status            VARCHAR(20) NOT NULL DEFAULT 'waiting'
                      CHECK (status IN ('waiting', 'matched', 'fulfilled'))
);

-- 4. Compatibility rules (static lookup table, 27 valid donor -> recipient pairs)
CREATE TABLE compatibility_rules (
    donor_blood_type     VARCHAR(3),
    recipient_blood_type VARCHAR(3),
    compatible           BOOLEAN NOT NULL,
    PRIMARY KEY (donor_blood_type, recipient_blood_type)
);

INSERT INTO compatibility_rules VALUES
('O-','O-',true), ('O-','O+',true), ('O-','A-',true), ('O-','A+',true),
('O-','B-',true), ('O-','B+',true), ('O-','AB-',true), ('O-','AB+',true),
('O+','O+',true), ('O+','A+',true), ('O+','B+',true), ('O+','AB+',true),
('A-','A-',true), ('A-','A+',true), ('A-','AB-',true), ('A-','AB+',true),
('A+','A+',true), ('A+','AB+',true),
('B-','B-',true), ('B-','B+',true), ('B-','AB-',true), ('B-','AB+',true),
('B+','B+',true), ('B+','AB+',true),
('AB-','AB-',true), ('AB-','AB+',true),
('AB+','AB+',true);

-- 5. Matches
CREATE TABLE matches (
    id           SERIAL PRIMARY KEY,
    donor_id     INT NOT NULL REFERENCES donors(id),
    recipient_id INT NOT NULL REFERENCES recipients(id),
    status       VARCHAR(20) NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'locked', 'confirmed', 'rejected')),
    confirmed_by INT REFERENCES users(id),
    created_at   TIMESTAMP DEFAULT NOW(),
    locked_at    TIMESTAMP
);

-- Safety net at database level: a donor / recipient can be in at most ONE live match.
-- Even if the application code had a bug, Postgres would refuse a double booking.
CREATE UNIQUE INDEX one_live_match_per_donor
    ON matches (donor_id)     WHERE status IN ('locked', 'confirmed');
CREATE UNIQUE INDEX one_live_match_per_recipient
    ON matches (recipient_id) WHERE status IN ('locked', 'confirmed');

-- Indexes that serve the matching query
CREATE INDEX idx_donors_available    ON donors (blood_type, organ_type) WHERE status = 'available';
CREATE INDEX idx_recipients_waiting  ON recipients (blood_type_needed)  WHERE status = 'waiting';
