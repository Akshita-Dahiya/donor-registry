-- Sample data for the demo. Run after schema.sql:  psql -U postgres -d donor_registry -f seed.sql
INSERT INTO users (name, role, phone) VALUES
 ('CMC Hospital Vellore',      'hospital',  '0416-2281000'),   -- id 1
 ('Apollo Hospital Chennai',   'hospital',  '044-28290200'),   -- id 2
 ('Arun Kumar',     'donor',     '9000000001'),               -- id 3
 ('Priya Nair',     'donor',     '9000000002'),               -- id 4
 ('Rahul Verma',    'donor',     '9000000003'),               -- id 5
 ('Sneha Iyer',     'donor',     '9000000004'),               -- id 6
 ('Karthik Raj',    'donor',     '9000000005'),               -- id 7
 ('Meena Devi',     'recipient', '9100000001'),               -- id 8
 ('Imran Sheikh',   'recipient', '9100000002'),               -- id 9
 ('Divya Menon',    'recipient', '9100000003');               -- id 10

INSERT INTO donors (user_id, blood_type, organ_type, latitude, longitude) VALUES
 (3, 'O-',  'blood',  12.9692, 79.1559),   -- Vellore
 (4, 'O+',  'blood',  13.0827, 80.2707),   -- Chennai
 (5, 'A+',  'blood',  12.9716, 77.5946),   -- Bengaluru
 (6, 'O-',  'kidney', 12.9165, 79.1325),   -- near Vellore
 (7, 'B+',  'blood',  13.1500, 79.9000);   -- near Chennai

INSERT INTO recipients (user_id, blood_type_needed, organ_needed, latitude, longitude, urgency) VALUES
 (8,  'A+',  'blood',  12.9500, 79.1300, 'critical'),   -- Vellore
 (9,  'AB+', 'blood',  13.0600, 80.2500, 'high'),       -- Chennai
 (10, 'B+',  'kidney', 12.9300, 79.1400, 'normal');     -- Vellore
