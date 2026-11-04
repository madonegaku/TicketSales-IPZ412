import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout, RequireRole } from "./Layout";
import { LoginPage, RegisterPage } from "./pages/Auth";
import { EventsPage } from "./pages/Events";
import { HallPage } from "./pages/Hall";
import { OrdersPage } from "./pages/Orders";

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
        <Route path="*" element={<p className="muted">Сторінку не знайдено.</p>} />
      </Route>
    </Routes>
  </BrowserRouter>
);
