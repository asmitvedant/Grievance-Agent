"""Hand-written, anonymised exemplar statements that seed the precedent store.

These are deliberately DIFFERENT from the evaluation cases in data/cases.jsonl so the urgency
kNN is never tested on the sentences it was seeded with. Reviewers can add more precedents
(from closed, anonymised cases) through the store.
"""
EXEMPLARS: list[tuple[str, str]] = [
    # routine
    ("My scholarship amount has not been credited for this semester.", "routine"),
    ("The hostel Wi-Fi has been down for two weeks and nobody has fixed it.", "routine"),
    ("I paid the exam fee twice and want a refund of the extra amount.", "routine"),
    ("My provisional certificate is being held back by the admin office.", "routine"),
    ("The results for the fourth semester were supposed to come out a month ago.", "routine"),
    ("The lab computers do not have the software we need for our practicals.", "routine"),
    ("My attendance is shown wrongly on the portal for the month of August.", "routine"),
    ("The college bus stopped coming to my stop without any notice.", "routine"),
    ("The library closes too early for students who have late classes.", "routine"),
    ("I was charged a development fee that was not mentioned in the prospectus.", "routine"),
    ("The water cooler on our floor has been broken since the start of term.", "routine"),
    ("Two of my exams are scheduled at the same time.", "routine"),
    # sensitive
    ("A senior keeps making me do his assignments and insults me in front of others in the hostel.", "sensitive"),
    ("A staff member made remarks about my caste when I went to submit my form.", "sensitive"),
    ("My lab partner keeps sending me messages that make me uncomfortable even after I asked him to stop.", "sensitive"),
    ("Seniors made the first-years stand in the corridor at night and shout their names.", "sensitive"),
    ("Girls in our batch are not given the same lab slots as boys.", "sensitive"),
    ("My request for a scribe as a student with a disability was refused.", "sensitive"),
    ("After I complained, the faculty member started marking me absent on purpose.", "sensitive"),
    ("People in my class mock my accent and where I come from every day.", "sensitive"),
    ("A professor commented on my clothes and appearance in a way that made me uncomfortable.", "sensitive"),
    ("I am being left out of group projects because of my religion.", "sensitive"),
    # high
    ("I don't want to be alive anymore.", "high"),
    ("Everyone would be better off if I just disappeared for good.", "high"),
    ("I have been thinking about ending my life.", "high"),
    ("I failed again and I keep wondering which building on campus is the tallest.", "high"),
    ("I have started giving my things away to my friends because I won't need them.", "high"),
    ("I can't take this anymore, I just want to sleep and never wake up.", "high"),
    ("My roommate said he will beat me up if I report him.", "high"),
    ("A senior hit me in the hostel last night.", "high"),
    ("Someone has been following me from the library to my room every night.", "high"),
    ("He touched me without my consent at the event.", "high"),
    ("They threatened to kill me if I told anyone.", "high"),
    ("I was forced into a room and assaulted by a group of seniors.", "high"),
    ("Ab jeene ka mann nahi karta, sab khatam karna chahta hoon.", "high"),
]
