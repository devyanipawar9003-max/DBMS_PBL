import streamlit as st

from db import execute, query_df
from ui import page_header, run_safely

page_header("Staff & Services", "Staff skills and weekly schedules; the service catalogue.")

DAYS = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
tab_staff, tab_skill, tab_svc = st.tabs(["👥 Staff", "🎓 Assign skill", "💅 Services"])

with tab_staff:
    df = query_df(
        """SELECT st.staff_id AS ID, st.full_name AS Name, st.designation AS Role, st.status AS Status,
                  GROUP_CONCAT(CONCAT(k.skill_name,' (',ss.proficiency_level,')')
                               ORDER BY ss.proficiency_level DESC SEPARATOR ', ') AS `Skills (level)`
             FROM staff st
             LEFT JOIN staff_skill ss ON ss.staff_id = st.staff_id
             LEFT JOIN skill k ON k.skill_id = ss.skill_id
            GROUP BY st.staff_id, st.full_name, st.designation, st.status ORDER BY st.staff_id""")
    st.dataframe(df, hide_index=True, width="stretch")
    sid = st.selectbox("Weekly schedule of", df.ID.tolist(), format_func=lambda i: df[df.ID == i].iloc[0].Name)
    sch = query_df("""SELECT day_of_week, shift_start, shift_end FROM staff_schedule
                       WHERE staff_id=%s ORDER BY day_of_week""", (int(sid),))
    sch["Day"] = sch.day_of_week.map(DAYS)
    off = [DAYS[d] for d in DAYS if d not in sch.day_of_week.tolist()]
    st.dataframe(sch[["Day", "shift_start", "shift_end"]].rename(columns={"shift_start": "From", "shift_end": "To"}),
                 hide_index=True)
    st.caption(f"Weekly off: {', '.join(off) or 'none'}")
    new_status = st.selectbox("Change status", ["ACTIVE", "ON_LEAVE", "INACTIVE"],
                              index=["ACTIVE", "ON_LEAVE", "INACTIVE"].index(df[df.ID == sid].iloc[0].Status))
    if st.button("Update status"):
        run_safely(lambda: execute("UPDATE staff SET status=%s WHERE staff_id=%s", (new_status, int(sid))),
                   "Staff status updated.", rerun=True)

with tab_skill:
    staff = query_df("SELECT staff_id, full_name FROM staff ORDER BY full_name")
    skills = query_df("SELECT skill_id, skill_name FROM skill ORDER BY skill_name")
    a = st.selectbox("Staff", staff.staff_id.tolist(), format_func=lambda i: staff[staff.staff_id == i].iloc[0].full_name)
    k = st.selectbox("Skill", skills.skill_id.tolist(), format_func=lambda i: skills[skills.skill_id == i].iloc[0].skill_name)
    lvl = st.slider("Proficiency (1–5)", 1, 5, 3)
    if st.button("Assign / update skill", type="primary"):
        run_safely(lambda: execute(
            """INSERT INTO staff_skill (staff_id, skill_id, proficiency_level) VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE proficiency_level = VALUES(proficiency_level)""",
            (int(a), int(k), lvl)), "Skill saved.", rerun=True)

with tab_svc:
    svc = query_df(
        """SELECT s.service_id AS ID, c.category_name AS Category, s.service_name AS Service,
                  k.skill_name AS `Needs skill`, s.duration_min AS `Minutes`, s.price AS `Price ₹`,
                  IF(s.is_active,'Yes','No') AS Active
             FROM service s JOIN service_category c ON c.category_id = s.category_id
             JOIN skill k ON k.skill_id = s.required_skill_id ORDER BY c.category_name, s.service_name""")
    st.dataframe(svc, hide_index=True, width="stretch")
    st.markdown("**Update price**")
    c1, c2, c3 = st.columns([3, 1, 1])
    sv = c1.selectbox("Service", svc.ID.tolist(), format_func=lambda i: svc[svc.ID == i].iloc[0].Service)
    price = c2.number_input("New price ₹", min_value=0.0, value=float(svc[svc.ID == sv].iloc[0]["Price ₹"]), step=50.0)
    c3.write("")
    if c3.button("Save price"):
        run_safely(lambda: execute("UPDATE service SET price=%s WHERE service_id=%s", (price, int(sv))),
                   "Price updated (past bills keep the price charged at the time).")
