CREATE DATABASE IF NOT EXISTS stbcet_hostel
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stbcet_hostel;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student','admin','staff') NOT NULL DEFAULT 'student',
    approved TINYINT(1) NOT NULL DEFAULT 0,
    phone VARCHAR(20),
    hostel_block VARCHAR(80),
    room_number VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    category VARCHAR(80) NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    hostel_block VARCHAR(80) NOT NULL,
    room_number VARCHAR(30) NOT NULL,
    priority ENUM('Low','Medium','High','Urgent') NOT NULL DEFAULT 'Medium',
    complaint_photo VARCHAR(255),
    status ENUM('Pending','Approved','Assigned','In Progress','Work Completed','Resolved','Closed','Rework') NOT NULL DEFAULT 'Pending',
    assigned_staff_id INT NULL,
    admin_remarks TEXT,
    maintenance_remarks TEXT,
    maintenance_photo VARCHAR(255),
    completed_at DATETIME NULL,
    verification_status ENUM('Pending','Verified','Rejected') NOT NULL DEFAULT 'Pending',
    verified_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_complaint_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_complaint_staff FOREIGN KEY (assigned_staff_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS complaint_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    changed_by INT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    remarks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_history_complaint FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
    CONSTRAINT fk_history_user FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
);

-- After the first run, use the Admin > Add Staff page to create staff.
-- The application creates a default admin automatically if none exists.
