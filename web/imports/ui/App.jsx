import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout, RequireRole } from "./Layout";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { EventsPage } from "./pages/Events";
import { AdminPage } from "./pages/Admin";
import { HallPage } from "./pages/Hall";
import { InspectorPage } from "./pages/Inspector";
import { OrdersPage } from "./pages/Orders";
import { NewEventPage, OrganizerPage } from "./pages/Organizer";

// Маршрути інтерфейсу. Права перевіряє і сторінка (RequireRole), і сервер (методи Meteor),
// і самі сервіси (роль у токені): приховане меню – лише зручність, не захист.
export const App = () => (
  <BrowserRouter>
    <Routes>
      <Route element={<Layout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<RequireRole><EventsPage /></RequireRole>} />
        <Route path="/events/:eventId" element={<RequireRole><HallPage /></RequireRole>} />
        <Route path="/orders" element={<RequireRole roles={["buyer"]}><OrdersPage /></RequireRole>} />
        <Route path="/organizer"
          element={<RequireRole roles={["organizer", "admin"]}><OrganizerPage /></RequireRole>} />
        <Route path="/organizer/new"
          element={<RequireRole roles={["organizer", "admin"]}><NewEventPage /></RequireRole>} />
        <Route path="/inspector"
          element={<RequireRole roles={["inspector", "admin"]}><InspectorPage /></RequireRole>} />
        <Route path="/admin" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />
        <Route path="*" element={<p className="muted">Сторінку не знайдено.</p>} />
      </Route>
    </Routes>
  </BrowserRouter>
);
