import { NavLink } from "react-router-dom";
import { useAuth } from "../auth";

// admin-dashboard change, task 9.3 — navigation between home, rule
// review, service catalog, source catalog, and the outdated-plan view.
export function NavBar() {
  const { signOut } = useAuth();

  return (
    <nav className="nav">
      <h1>GovAssist Admin</h1>
      <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
        Home
      </NavLink>
      <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
        Rule review
      </NavLink>
      <NavLink to="/services" className={({ isActive }) => (isActive ? "active" : "")}>
        Services
      </NavLink>
      <NavLink to="/sources" className={({ isActive }) => (isActive ? "active" : "")}>
        Sources
      </NavLink>
      <NavLink to="/plans" className={({ isActive }) => (isActive ? "active" : "")}>
        Outdated plans
      </NavLink>
      <button className="secondary" onClick={signOut}>
        Sign out
      </button>
    </nav>
  );
}
