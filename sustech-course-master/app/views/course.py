from flask import Blueprint,render_template,abort,redirect,url_for,request,abort,jsonify
from flask_login import login_required
from flask_babel import gettext as _
from app.models import *
from app.forms import ReviewForm, CourseForm
from app import db
from app.utils import sanitize
from sqlalchemy import or_, func
import json
import os
import datetime

course = Blueprint('course',__name__)

deptlist = [
     [1, '通识与学科基础部'],
     [7, '网络通识课程部'],
     [20, '工学院'],
     [30, '生命科学学院'],
     [40, '商学院'],
     [50, '人文社会科学学院'],
     [55, '创新创业学院'],
     [58, '医学院'],
     [60, '语言中心'],
     [61, '创新创意设计学院'],
     [63, '公共卫生及应急管理学院'],
     [64, '深圳理工大学（筹）'],
     [65, '思想政治教育与研究中心'],
     [70, '公共基础课部'],
     [75, '南方科技大学伦敦国王学院医学院'],
     [150, '学生工作部'],
     [170, '研究生院'],
     [500, '高等教育研究中心'],
     [710, '量子科学与工程研究院'],
     [5802, '附属医院'],
     [10010, '数学系'],
     [10020, '物理系'],
     [10030, '化学系'],
     [10080, '地球与空间科学系'],
     [10090, '统计与数据科学系'],
     [20010, '电子与电气工程系'],
     [20020, '材料科学与工程系'],
     [20030, '环境科学与工程学院'],
     [20040, '海洋科学与工程系'],
     [20050, '力学与航空航天工程系'],
     [20060, '机械与能源工程系'],
     [20070, '计算机科学与工程系'],
     [20100, '生物医学工程系'],
     [20150, '系统设计与智能制造学院'],
     [20160, '深港微电子学院'],
     [30010, '生物系'],
     [40010, '金融系'],
     [40020, '信息系统与管理工程系'],
     [50010, '人文科学中心'],
     [50020, '社会科学中心'],
     [58010, '医学神经科学系'],
     [58020, '药理学系'],
     [58030, '人类细胞生物和遗传学系'],
     [58040, '生物化学系'],
     [70010, '艺术中心'],
     [70020, '体育中心']
]

course_type_dict = {
    'ucug': ['UCUG', '通识教育课程'],
    'ucmp': ['UCMP', '通识教育课程'],
    'ufug': ['UFUG', '通识教育课程'],
    'aiaa': ['AIAA', '人工智能与自动化'],
    'dsaa': ['DSAA', '数据科学与分析'],
    'smmg': ['SMMG', '智能制造'],
    'amat': ['AMAT', '先进材料'],
    'bsbe': ['BSBE', '生物科学与生物医学工程'],
    'cmaa': ['CMAA', '计算媒体与艺术'],
    'eoas': ['EOAS', '地球与海洋大气科学'],
    'ftec': ['FTEC', '金融科技'],
    'funh': ['FUNH', '功能枢纽'],
    'infh': ['INFH', '信息枢纽'],
    'intr': ['INTR', '跨学科研究'],
    'iota': ['IOTA', '物联网'],
    'ipen': ['IPEN', '智能电力与能源网络'],
    'lang': ['LANG', '语言教育'],
    'mics': ['MICS', '微电子'],
    'pdev': ['PDEV', '专业发展'],
    'pled': ['PLED', '公共领导力'],
    'roas': ['ROAS', '机器人'],
    'seen': ['SEEN', '可持续能源与环境'],
    'soch': ['SOCH', '社会枢纽'],
    'sysh': ['SYSH', '系统枢纽'],
    'ugod': ['UGOD', '本科生办公室']
}


@course.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    sort_by = request.args.get('sort_by', None, type=str)
    course_type = request.args.get('course_type', None, type=str)
    course_query = Course.query

    # 课程类型
    if course_type in course_type_dict.keys():
        # 修改查询逻辑，先获取符合条件的课程ID
        course_ids = db.session.query(Course.id).join(CourseTerm).filter(
            or_(CourseTerm.course_type.in_(course_type_dict[course_type]), 
                CourseTerm.join_type.in_(course_type_dict[course_type]))
        ).distinct().all()
        course_ids = [id[0] for id in course_ids]
        course_query = Course.query.filter(Course.id.in_(course_ids))

    # 排序方式
    if sort_by == 'popular':
        # sort by review_count
        courses_page = course_query.join(CourseRate).order_by(CourseRate.review_count.desc(), CourseRate._rate_average.desc()).paginate(page=page, per_page=per_page)
    else:
        # default sort by rating
        courses_page = course_query.join(CourseRate).order_by(Course.QUERY_ORDER()).paginate(page=page, per_page=per_page)

    return render_template('course-index.html', courses=courses_page,
            course_type=course_type, course_type_dict=course_type_dict, sort_by=sort_by,
            title='课程列表', deptlist=deptlist, this_module='course.index')


@course.route('/<int:course_id>/')
def view_course(course_id):

    course = Course.query.get(course_id)
    if not course:
        abort(404)
    course.access_count += 1
    course.save_without_edit()

    related_courses = Course.query.filter_by(name=course.name).all()
    teacher = course.teacher

    if teacher:
        same_teacher_courses = teacher.courses
    else:
        same_teacher_courses = None

    # sort and filter review by url parameters
    ordering = request.args.get('sort_by', 'upvote', type=str)
    term = request.args.get('term', None, type=str)
    rating = request.args.get('rating', None, type=int)

    sort_dict = {
            'upvote': '点赞最多',
            'pubtime_desc': '最新点评',
            'pubtime': '最旧点评',
            'score_desc': '评分: 高-低',
            'score': '评分: 低-高',
            }

    query = Review.query.filter_by(course_id=course.id)

    # get terms list which have review
    review_term_list = course.review_term_list

    # filter review by term
    if term in review_term_list:
        query = query.filter(Review.term==term)

    # filter review by rating star
    if rating and 1 <= rating <= 5:
        query = query.filter(or_(Review.rate==2*rating-1, Review.rate==2*rating))

    # sort review by keyword
    if ordering == 'pubtime_desc':
        query = query.order_by(Review.publish_time.desc())
    elif ordering == 'pubtime':
        query = query.order_by(Review.publish_time)
    elif ordering == 'score_desc':
        query = query.order_by(Review.rate.desc(), Review.publish_time.desc())
    elif ordering == 'score':
        query = query.order_by(Review.rate, Review.publish_time.desc())
    else:
        # default sort_by upvote number
        query = query.order_by(Review.upvote_count.desc(), Review.publish_time.desc())

    reviews = query.all()
    review_num = len(reviews)

    #get client ip
    client_ip = request.access_route[-1]
    # get current date in YYYYMMDD HH:MM:SS format
    current_date = datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')


    return render_template('course.html', course=course, course_rate = course.course_rate, reviews=reviews,
            related_courses=related_courses, teacher=teacher, same_teacher_courses=same_teacher_courses,
            user=current_user, sort_by=ordering, term=term, rating=rating, sort_dict=sort_dict,
            review_num=review_num, _anchor='my_anchor',
            title=course.name_with_teachers_short,
            latest_score = course.latest_score,
            score_type_pf = course.score_type_pf,
            score_semester = course.score_semester,
            description=str(course.rate.average_rate) + ' 分，' + str(course.rate.review_count) + ' 人评价',
            client_ip=client_ip,
            current_date=current_date)

@course.route('/<int:course_id>/material/', methods=['GET'])
@login_required
def render_course_materials(course_id):
    course = Course.query.get(course_id)
    if not course:
        abort(404)
    return render_template('course-material-file-browser.html', course=course, title='Course Material - ' + course.name, course_id=course_id)



@course.route('/<int:course_id>/upvote/', methods=['POST'])
@login_required
def upvote(course_id):
    course = Course.query.get(course_id)
    if not course or course.upvoted:
        return jsonify(ok=False)
    if course.downvoted:
        course.un_downvote()
    ok = course.upvote()
    return jsonify(ok=ok, count=course.upvote_count)

@course.route('/<int:course_id>/undo-upvote/', methods=['POST'])
@login_required
def undo_upvote(course_id):
    course = Course.query.get(course_id)
    if not course or not course.upvoted:
        return jsonify(ok=False)
    ok = course.un_upvote()
    return jsonify(ok=ok, count=course.upvote_count)

@course.route('/<int:course_id>/downvote/', methods=['POST'])
@login_required
def downvote(course_id):
    course = Course.query.get(course_id)
    if not course or course.downvoted:
        return jsonify(ok=False)
    if course.upvoted:
        course.un_upvote()
    ok = course.downvote()
    return jsonify(ok=ok, count=course.downvote_count)

@course.route('/<int:course_id>/undo-downvote/', methods=['POST'])
@login_required
def undo_downvote(course_id):
    course = Course.query.get(course_id)
    if not course or not course.downvoted:
        return jsonify(ok=False)
    ok = course.un_downvote()
    return jsonify(ok=ok, count=course.downvote_count)

@course.route('/<int:course_id>/follow/', methods=['POST'])
@login_required
def follow(course_id):
    course = Course.query.get(course_id)
    if not course or course.following:
        return jsonify(ok=False)
    ok = course.follow()
    return jsonify(ok=ok, count=course.follow_count)

@course.route('/<int:course_id>/unfollow/', methods=['POST'])
@login_required
def unfollow(course_id):
    course = Course.query.get(course_id)
    if not course or not course.following:
        return jsonify(ok=False)
    ok = course.unfollow()
    return jsonify(ok=ok, count=course.follow_count)

@course.route('/<int:course_id>/join/', methods=['POST'])
@login_required
def join(course_id):
    course = Course.query.get(course_id)
    if not course or course.joined:
        return jsonify(ok=False)
    ok = course.join()
    return jsonify(ok=ok)

@course.route('/<int:course_id>/quit/',
methods=['POST'])
@login_required
def quit(course_id):
    course = Course.query.get(course_id)
    if not course or not course.joined:
        return jsonify(ok=False)
    ok = course.quit()
    return jsonify(ok=ok)

@course.route('/<int:course_id>/reviews/')
def reviews(course_id):
    course = Course.query.get(course_id)
    if not course:
        abort(404)

    try:
        page = int(request.args.get('page', 1))
    except:
        page = 1

    reviews = course.reviews.paginate(page=page, per_page=10)
    if reviews.total:
        str = ''
        for item in reviews.items:
            str += item.content + '<a href=' + url_for('review.edit_review', review_id=item.id) +'>Edit</a><br>'
        return str
    else:
        return 'No reviews'

@course.route('/s/<string:id>/')
def student_courses(id):
    student = Student.query.get(id)
    if student:
        page = request.args.get('page',1,type=int)
        per_page = request.args.get('perpage',15,type=int)
        courses_page = student.courses_joined.join(CourseRate).order_by(Course.QUERY_ORDER()).paginate(page=page,per_page=per_page)
        return render_template('list-courses.html',student=student,courses=courses_page)
    else:
        return render_template('feedback.html',status=False,message=_('We can\'t find the User!'))

@course.route('/t/<int:id>/')
def teacher_courses(id):
    teacher = Teacher.query.get(id)
    if teacher:
        page = request.args.get('page',1,type=int)
        per_page = request.args.get('perpage',15,type=int)
        courses_page = teacher.courses.join(CourseRate).order_by(Course.QUERY_ORDER()).paginate(page=page,per_page=per_page)
        return render_template('list-courses.html',teacher=teacher,courses=courses_page)
    else:
        return render_template('feedback.html',status=False,message=_('We can\'t find the User!'))

@course.route('/c/<string:name>/')
def same_name_courses(name):
    name = name.strip()
    page = request.args.get('page',1,type=int)
    per_page = request.args.get('perpage',15,type=int)
    courses_page = Course.query.filter_by(name=name).join(CourseRate).order_by(Course.QUERY_ORDER()).paginate(page=page,per_page=per_page)
    if courses_page.items:
        return render_template('list-courses.html',course_name=name,courses=courses_page)
    else:
        return render_template('list-courses.html',course_name=name,courses=courses_page,message=_("No course called %(name)s found!",name=name))

@course.route('/goto/<string:cno>')
def course_redirect_cno(cno):
    cno = cno.strip()
    course_class = CourseClass.query.filter_by(cno=cno).order_by(CourseClass.term.desc()).all()
    if len(course_class) > 0:
        return redirect(url_for('course.view_course', course_id=course_class[0].course_id))
    else:
        abort(404)

@course.route('/goto/<string:cno>/<int:term>')
def course_redirect_cno_term(cno, term):
    cno = cno.strip()
    term = int(term)
    course_class = CourseClass.query.filter_by(cno=cno, term=term).all()
    if len(course_class) > 0:
        return redirect(url_for('course.view_course', course_id=course_class[0].course_id))
    else:
        abort(404)



@course.route('/<int:course_id>/profile_history/', methods=['GET'])
@login_required
def profile_history(course_id):
    course = Course.query.get(course_id)
    if not course:
        abort(404)
    return render_template('course-profile-history.html', course=course, title='课程信息编辑历史 - ' + course.name_with_teachers_short)


@course.route('/new/',methods=['GET','POST'])
@course.route('/<int:course_id>/edit/',methods=['GET','POST'])
@login_required
def edit_course(course_id=None):
    if course_id:
        course = Course.query.get(course_id)
    else:
        course = Course()
    if not course:
        abort(404)
    course_form = CourseForm(formdata=request.form, obj=course)
    if course_form.validate_on_submit():
        course_form.introduction.data = sanitize(course_form.introduction.data)
        course_form.populate_obj(course)
        if not course.homepage.startswith('http'):
            course.homepage = 'http://' + course.homepage
        if current_user.is_admin:
            course.admin_announcement = sanitize(course_form.admin_announcement.data)
        course.save()

        info_history = CourseInfoHistory()
        info_history.save(course, current_user) 

        db.session.commit()
        return redirect(url_for('course.view_course', course_id=course.id))
    return render_template('course-edit.html', form=course_form, course=course, title='编辑课程信息 - ' + course.name_with_teachers_short)


@course.route('/<int:course_id>/remove_teacher/', methods=['POST'])
@login_required
def remove_teacher(course_id):
    if not current_user.is_admin:
        abort(403)
    teacher_id = request.form.get('teacher_id')
    if not teacher_id:
        return jsonify(ok=False, message=_('Teacher ID Not Specified'))
    course = Course.query.get(course_id)
    if not course:
        return jsonify(ok=False, message=_('Course Not Found'))
    ok = False
    new_teachers = []
    for teacher in course.teachers:
        if str(teacher.id) == teacher_id:
            ok = True
        else:
            new_teachers.append(teacher)

    if not ok:
        return jsonify(ok=False, message=_('Teacher Not Found In Course'))
    course.teachers = new_teachers
    db.session.commit()
    return jsonify(ok=True)


@course.route('/<int:course_id>/add_teacher/', methods=['POST'])
@login_required
def add_teacher(course_id):
    if not current_user.is_admin:
        abort(403)
    teacher_id = request.form.get('teacher_id')
    if not teacher_id:
        return jsonify(ok=False, message=_('Teacher ID Not Specified'))
    course = Course.query.get(course_id)
    if not course:
        return jsonify(ok=False, message=_('Course Not Found'))
    teacher = Teacher.query.get(teacher_id)
    if not teacher:
        return jsonify(ok=False, message=_('Teacher ID Not Found'))
    if teacher in course.teachers:
        return jsonify(ok=False, message=_('Teacher Already Exists In Course'))
    course.teachers.append(teacher)
    db.session.commit()
    return jsonify(ok=True)
