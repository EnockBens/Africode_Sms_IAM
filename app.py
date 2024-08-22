from flask import Flask, render_template,flash,url_for,redirect,request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_security import Security, UserMixin, RoleMixin, login_required, SQLAlchemyUserDatastore, hash_password, current_user,roles_required
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

roles_users = db.Table('roles_users',
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
    
    # backref here automatically creates an `enrollments` attribute on the `User` model
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
    
    # backref here automatically creates a `course` attribute on the `Enrollment` model
    enrollments = db.relationship('Enrollment', backref='course')

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    
    # `backref` automatically handles the reverse relationships for `student` and `course`
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

@app.before_request
def restrict_authenticated_user():
    # List of endpoints to restrict
    restricted_endpoints = ['security.login', 'security.register']

    # Check if the user is authenticated and trying to access a restricted endpoint
    if current_user.is_authenticated and request.endpoint in restricted_endpoints:
        flash('You are already logged in.', 'info')
        return redirect(url_for('index'))  # Redirect to your desired page (e.g., index)


# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)
mail = Mail(app)

@app.route('/')
@login_required
def index():
    if current_user.has_role('Admin'):
        # Admin sees the total number of teachers, students, and courses
        courses_count = Course.query.count()
        students_count = User.query.join(User.roles).filter(Role.name == 'Student').count()
        teachers_count = User.query.join(User.roles).filter(Role.name == 'Teacher').count()
    elif current_user.has_role('Teacher'):
        # Teacher sees the total number of courses they are teaching and the students they are teaching
        courses_count = Course.query.filter_by(teacher_id=current_user.id).count()
        students_count = User.query.join(Enrollment).join(Course).filter(Course.teacher_id == current_user.id).distinct().count()
        teachers_count = None  # Not applicable for teachers, so set to None or 0
    elif current_user.has_role('Student'):
        # Student sees the total number of courses they are taking and the total number of teachers teaching them
        courses_count = Enrollment.query.filter_by(student_id=current_user.id).count()
        teachers_count = Course.query.join(Enrollment).filter(Enrollment.student_id == current_user.id).distinct(Course.teacher_id).count()
        students_count = None  # Not applicable for students, so set to None or 0
    else:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    return render_template('index.html',
                           course=Course.query.first(),  # For displaying a course
                           courses_count=courses_count,
                           students_count=students_count,
                           teachers_count=teachers_count,
                           title='Dashboard')

 



@app.route('/courses')
@login_required
def courses():
    if current_user.has_role('Admin'):
        courses = Course.query.all()  # Admin sees all courses
    elif current_user.has_role('Teacher'):
        courses = Course.query.filter_by(teacher_id=current_user.id).all()  # Teacher sees only courses they teach
    elif current_user.has_role('Student'):
        courses =  Course.query.all()  # Student sees all courses
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
        # Admin can see course name, teacher, students, grades, and remarks
        context = {
            'role': 'Admin',
            'course': course,
            'teacher': course.teacher,
            'enrollments': enrollments
        }
    elif current_user.has_role('Teacher'):
        # Teacher can see course name, student names, and their grades
        context = {
            'role': 'Teacher',
            'course': course,
            'enrollments': enrollments
        }
    elif current_user.has_role('Student'):
        # Student can see all courses they are enrolled in, with course name, teacher, grade, and remark
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


@app.route('/create_course',methods=['POST','GET'])
@roles_required('Admin')
def create_course():
    if request.method == 'POST':
        name = request.form.get('name')
        teacher_id = request.form.get('teacher_id')
        course = Course(name=name, teacher_id=teacher_id)
        db.session.add(course)
        db.session.commit()
        flash('Course created successfully','success')
        return redirect(url_for('courses'))
    else:
        teachers = User.query.join(roles_users).join(User.roles).filter(Role.name == 'Teacher').all()
        return render_template('create_course.html', title='Create Course | SMS', teachers=teachers)




@app.route('/enroll/<int:course_id>', methods=['GET','POST'])
@roles_required('Student')
def enroll(course_id):
    course = Course.query.get_or_404(course_id)    
    
     # Check if the student is already enrolled in the course
    existing_enrollment = Enrollment.query.filter_by(student_id=current_user.id, course_id=course_id).first()

    if existing_enrollment:  # Student is already enrolled in the course
        flash('You are already enrolled in this course','warning')
        return redirect(url_for('courses'))
    else:
        enrollment = Enrollment(course_id=course_id, student_id=current_user.id)
        db.session.add(enrollment)
        db.session.commit()
        flash('Enrollment successful','success')
    return redirect(url_for('course_details',course_id=course.id))#check here


@app.route('/manage_courses', methods=['GET', 'POST'])
@login_required
@roles_required('Admin')  # Ensure only teachers can access this route
def manage_courses():
    if request.method == 'POST':
        # Handle course creation or update
        course_id = request.form.get('course_id')
        course_name = request.form.get('course_name')
        
        if course_id:
            # Update existing course
            course = Course.query.get(course_id)
            if course:
                course.name = course_name
                db.session.commit()
                flash('Course updated successfully!', 'success')
            else:
                flash('Course not found!', 'danger')
        # else:
        #     # Create a new course
        #     new_course = Course(name=course_name, teacher_id=current_user.id)
        #     db.session.add(new_course)
        #     db.session.commit()
        #     flash('Course created successfully!', 'success')
        
        return redirect(url_for('manage_courses'))

    # GET request: Show the form for creating or updating courses
    courses = Course.query.all()
    return render_template('manage_courses.html', courses=courses)

@app.route('/manage_students', methods=['GET', 'POST'])
@roles_required('Teacher')
def manage_students():
    # Get all courses that the current teacher is teaching
    courses = Course.query.filter_by(teacher_id=current_user.id).all()

    # Get all enrollments for those courses
    enrollments = Enrollment.query.join(Course).filter(Course.teacher_id == current_user.id).all()
    
    # Handle form submission
    if request.method == 'POST':
        enrollment_id = request.form.get('enrollment_id')
        grade = request.form.get('grade')
        remark = request.form.get('remark')
        
        enrollment = Enrollment.query.get_or_404(enrollment_id)
        
        # Ensure the teacher is only grading their own students
        if enrollment.course.teacher_id == current_user.id:
            try:
                grade_value = float(grade)
                if 0 <= grade_value <= 100:  # Example range check
                    enrollment.grade = grade_value
                    enrollment.remark = remark
                    db.session.commit()
                    flash('Grade and remark submitted successfully', 'success')
                else:
                    flash('Grade must be between 0 and 100', 'warning')
            except ValueError:
                flash('Invalid grade value', 'danger')
        else:
            flash('Invalid enrollment', 'danger')
    
    return render_template('manage_students.html', courses=courses, enrollments=enrollments)




@app.route('/register_user',methods=['POST','GET'])
@roles_required('Admin')
def register_user():
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        role = form.role.data

        # Check if the user already exists
        if user_datastore.find_user(email=email):
            flash('Email is already registered','warning')
            return redirect(url_for('register_user'))

         # Find the role in the database
        role = user_datastore.find_role(role)
        if role is None:
            flash(f'Role "{role}" does not exist.', 'danger')
            return redirect(url_for('register_user'))
        
      # Hash the password and create the user
        hashed_password = hash_password(password)
        user = user_datastore.create_user(email=email, password=hashed_password)
        
        
        # Add role to user
        user_datastore.add_role_to_user(user,role)
        
        db.session.commit()
        flash('User registered successfully','success')
        return redirect(url_for('index'))
    
    return render_template('register_user.html', title='Register User | SMS', form=form) 
    
@app.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
@roles_required('Admin')  # Ensure only admins can delete courses
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('manage_courses'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

         # create roles
        user_datastore.find_or_create_role(name='Admin', description='Administrator')
        user_datastore.find_or_create_role(name='Teacher', description='Teacher')
        user_datastore.find_or_create_role(name='Student', description='Student')
        # Create users
        if not user_datastore.find_user(email='bensonkings81@gmail.com'):
            hashed_password = hash_password('Kipkorir2015')
            user_datastore.create_user(email='bensonkings81@gmail.com', password=hashed_password, roles=[user_datastore.find_role('Admin')])
            db.session.commit()

        if not user_datastore.find_user(email='enockbenz294@gmail.com'):
            hashed_password = hash_password('Kipkorir2015')
            user_datastore.create_user(email='enockbenz294@gmail.com', password=hashed_password, roles=[user_datastore.find_role('Teacher')])
            db.session.commit()

        if not user_datastore.find_user(email='josephtaaa@gmail.com'):
                    hashed_password = hash_password('Kipkorir2015')
                    user_datastore.create_user(email='josephtaaa@gmail.com', password=hashed_password, roles=[user_datastore.find_role('Student')])
                    db.session.commit()


    app.run(debug=True,port='6000')

