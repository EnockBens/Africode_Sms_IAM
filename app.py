import os
from flask import Flask, render_template, flash, send_from_directory, url_for, redirect, request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, UserMixin, RoleMixin, login_required, SQLAlchemyUserDatastore, hash_password, current_user, roles_required
from flask_mailman import Mail
import config
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError

app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)
Bootstrap5(app)
migrate = Migrate(app, db)

roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean(), default=True)
    confirmed_at = db.Column(db.DateTime())
    fs_uniquifier = db.Column(db.String(255), unique=True)
    
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))
    webauth = db.relationship('WebAuth', backref='user', uselist=False)
    
    enrollments = db.relationship('Enrollment', backref='student')
    
    @property
    def enrolled_courses(self):
        return [enrollment.course for enrollment in self.enrollments]

class WebAuth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    teacher = db.relationship('User', backref='courses_taught')
    
    enrollments = db.relationship('Enrollment', backref='course')

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    
    grade = db.Column(db.Float, nullable=True)

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('Student', 'Student'), ('Teacher', 'Teacher'), ('Admin', 'Admin')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered.')

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)
mail = Mail(app)

@app.route('/')
@login_required
def index():
    course = Course.query.first()
    if course is None:
        flash('No courses available.', 'warning')
        course = None

    if current_user.has_role('Admin'):
        courses_count = Course.query.count()
        students_count = User.query.join(User.roles).filter(Role.name == 'Student').count()
        teachers_count = User.query.join(User.roles).filter(Role.name == 'Teacher').count()
    elif current_user.has_role('Teacher'):
        courses_count = Course.query.filter_by(teacher_id=current_user.id).count()
        students_count = User.query.join(Enrollment).join(Course).filter(Course.teacher_id == current_user.id).distinct().count()
        teachers_count = None
    elif current_user.has_role('Student'):
        courses_count = Enrollment.query.filter_by(student_id=current_user.id).count()
        teachers_count = Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id).distinct(Course.teacher_id).count()
        students_count = None
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    return render_template('index.html', course=course, courses_count=courses_count,
                           students_count=students_count, teachers_count=teachers_count, title='Dashboard')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.jpg')

@app.route('/courses')
@login_required
def courses():
    if current_user.has_role('Admin'):
        courses = Course.query.all()
    elif current_user.has_role('Teacher'):
        courses = Course.query.filter_by(teacher_id=current_user.id).all()
    elif current_user.has_role('Student'):
        courses = Course.query.all()
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('courses.html', title='Courses | SMS', courses=courses)

@app.route('/courses/<int:course_id>')
@login_required
def course_details(course_id):
    course = Course.query.get_or_404(course_id)
    enrollments = Enrollment.query.filter_by(course_id=course_id).all()
    
    if current_user.has_role('Admin'):
        context = {
            'role': 'Admin',
            'course': course,
            'teacher': course.teacher,
            'enrollments': enrollments
        }
    elif current_user.has_role('Teacher'):
        context = {
            'role': 'Teacher',
            'course': course,
            'enrollments': enrollments
        }
    elif current_user.has_role('Student'):
        enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
        context = {
            'role': 'Student',
            'course': course,
            'enrollments': enrollments
        }
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    return render_template('course_details.html', **context, title='Course Details | SMS')

@app.route('/create_course', methods=['POST', 'GET'])
@roles_required('Admin')
def create_course():
    if request.method == 'POST':
        name = request.form.get('name')
        teacher_id = request.form.get('teacher_id')
        course = Course(name=name, teacher_id=teacher_id)
        db.session.add(course)
        db.session.commit()
        flash('Course created successfully', 'success')
        return redirect(url_for('courses'))
    else:
        teachers = User.query.join(roles_users).join(User.roles).filter(Role.name == 'Teacher').all()
        return render_template('create_course.html', title='Create Course | SMS', teachers=teachers)

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
@roles_required('Student')
def enroll(course_id):
    course = Course.query.get_or_404(course_id)    
    
    existing_enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()

    if existing_enrollment:
        flash('You are already enrolled in this course', 'warning')
        return redirect(url_for('courses'))
    else:
        enrollment = Enrollment(course_id=course_id, student_id=current_user.id)
        db.session.add(enrollment)
        db.session.commit()
        flash('Enrollment successful', 'success')
    return redirect(url_for('course_details', course_id=course.id))

@app.route('/manage_courses', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')
def manage_courses():
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        course_name = request.form.get('course_name')
        
        if course_id:
            course = Course.query.get(course_id)
            if course:
                course.name = course_name
                db.session.commit()
                flash('Course updated successfully!', 'success')
            else:
                flash('Course not found!', 'danger')
        return redirect(url_for('manage_courses'))

    courses = Course.query.all()
    return render_template('manage_courses.html', courses=courses)

@app.route('/manage_students', methods=['GET', 'POST'])
@roles_required('Teacher')
def manage_students():
    courses = Course.query.filter_by(teacher_id=current_user.id).all()
    enrollments = Enrollment.query.join(Course).filter(Course.teacher_id == current_user.id).all()
    
    if request.method == 'POST':
        enrollment_id = request.form.get('enrollment_id')
        grade = request.form.get('grade')
        remark = request.form.get('remark')
        
        enrollment = Enrollment.query.get_or_404(enrollment_id)
        
        if enrollment.course.teacher_id == current_user.id:
            enrollment.grade = grade
            db.session.commit()
            flash('Grade updated successfully', 'success')
        else:
            flash('Access denied.', 'danger')
        return redirect(url_for('manage_students'))
    
    return render_template('manage_students.html', courses=courses, enrollments=enrollments, title='Manage Students')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = user_datastore.create_user(email=form.email.data, password=hash_password(form.password.data))
        role = Role.query.filter_by(name=form.role.data).first()
        user_datastore.add_role_to_user(user, role)
        db.session.commit()
        flash('You have successfully registered!', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', form=form, title='Register')

# Catch-All Route
@app.route('/<path:path>')
def catch_all(path):
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run()
