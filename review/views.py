import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http.response import JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404

from data.files import get_text, get_submission_text
from data.models import Course, Submission, Comparison
from review.decorators import access_resource
from review.forms import ExerciseForm, ExerciseTokenizerForm


logger = logging.getLogger("radar.review")


@login_required
def index(request):
    return render(request, "review/index.html", {
        "hierarchy": (("Radar", None),),
        "courses": Course.objects.get_available_courses(request.user)
    })


@access_resource
def course(request, course_key=None, course=None):
    return render(request, "review/course.html", {
        "hierarchy": (("Radar", reverse("index")), (course.name, None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def course_histograms(request, course_key=None, course=None):
    return render(request, "review/course_histograms.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_key": course.key })),
                      ("Histograms", None)),
        "course": course,
        "exercises": course.exercises.all()
    })


@access_resource
def exercise(request, course_key=None, exercise_key=None, course=None, exercise=None):
    return render(request, "review/exercise.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_key": course.key })),
                      (exercise.name, None)),
        "course": course,
        "exercise": exercise
    })


@access_resource
def exercise_json(request, course_key=None, exercise_key=None, student_key=None, course=None, exercise=None, student=None):
    LIMIT = 300
    def submission_data(s):
        return { "student": s.student.key, "id": s.id,
            "created": s.created, "grade": s.grade, "length": s.authored_token_count }
    data = map(lambda c: {
        "a": submission_data(c.submission_a),
        "b": submission_data(c.submission_b),
        "similarity": c.similarity,
        "review": c.review_class,
        "url": reverse("review.views.comparison",
            kwargs={ "course_key": course.key, "exercise_key": exercise.key,
                "ak": c.submission_a.student.key, "bk": c.submission_b.student.key, "ck": c.pk })
    }, exercise.comparisons[:LIMIT] if student is None else exercise.comparisons_for_student(student)[:LIMIT])
    return JsonResponse(list(data), safe=False)


@access_resource
def comparison(request, course_key=None, exercise_key=None, ak=None, bk=None, ck=None, course=None, exercise=None):
    comparison = get_object_or_404(Comparison, submission_a__exercise=exercise, pk=ck)
    a = comparison.submission_a
    b = comparison.submission_b
    if a.student.key != ak or b.student.key != bk:
        raise Http404()

    if request.method == "POST":
        result = "review" in request.POST and comparison.update_review(request.POST["review"])
        if request.is_ajax():
            return JsonResponse({ "success": result })

    reverse_flag = "reverse" in request.GET

    return render(request, "review/comparison.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_key": course.key })),
                      (exercise.name, reverse("review.views.exercise",
                                              kwargs={ "course_key": course.key, "exercise_key": exercise.key })),
                      ("%s vs %s" % (ak, bk), None)),
        "course": course,
        "exercise": exercise,
        "comparison": comparison,
        "source_a": get_submission_text(a),
        "source_b": get_submission_text(b),
        "compared": b if reverse_flag else a,
        "reverse": reverse_flag
    })


@access_resource
def exercise_settings(request, course_key=None, exercise_key=None, course=None, exercise=None):
    if request.method == "POST":
        if "save" in request.POST:
            form = ExerciseForm(request.POST)
            if form.is_valid():
                form.save(exercise)
                return redirect("review.views.course", course_key=course.key)
        if "save_and_clear" in request.POST:
            form_tokenizer = ExerciseTokenizerForm(request.POST)
            if form_tokenizer.is_valid():
                form_tokenizer.save(exercise)
                return redirect("review.views.course", course_key=course.key)
    else:
        form = ExerciseForm({"name": exercise.name })
        form_tokenizer = ExerciseTokenizerForm({
            "tokenizer": exercise.tokenizer,
            "minimum_match_tokens": exercise.minimum_match_tokens,
            "template": get_text(exercise, ".template")
        })
    return render(request, "review/exercise_settings.html", {
        "hierarchy": (("Radar", reverse("index")),
                      (course.name, reverse("review.views.course", kwargs={ "course_key": course.key })),
                      ("%s settings" % (exercise.name), None)),
        "course": course,
        "exercise": exercise,
        "form": form,
        "form_tokenizer": form_tokenizer
    })
