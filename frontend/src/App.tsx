import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AuthGuard, RoleGuard } from './components/AuthGuard';
import { Layout } from './components/Layout';
import { Login } from './components/Login';
import { CourseDashboard } from './components/CourseDashboard';
import { StudentProfile } from './components/StudentProfile';
import { TeacherHome } from './components/TeacherHome';
import { TeacherProfile } from './components/TeacherProfile';

import { useAuth } from './context/AuthContext';

const HomeRedirect: React.FC = () => {
  const { user } = useAuth();
  if (!user || !user.allowed_courses || user.allowed_courses.length === 0) {
    return <Navigate to="/login" replace />;
  }
  if (user.is_teacher) {
    return <TeacherHome />;
  }
  return <Navigate to={`/course/${user.allowed_courses[0]}/student/${user.moodle_user_id}`} replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route element={<AuthGuard />}>
            <Route element={<Layout />}>
              <Route path="/" element={<HomeRedirect />} />
              
              <Route element={<RoleGuard requireTeacher={true} />}>
                <Route path="/course/:courseId" element={<CourseDashboard />} />
                <Route path="/profile" element={<TeacherProfile />} />
              </Route>
              
              <Route path="/course/:courseId/student/:studentId" element={<StudentProfile />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
