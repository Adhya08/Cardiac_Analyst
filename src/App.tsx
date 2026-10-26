import { useStore } from './store/useStore';
import { AppShell } from './components/AppShell';
import { OverviewMode } from './modes/OverviewMode';
import { RoutineMode } from './modes/RoutineMode';
import { ECGMode } from './modes/ECGMode';
import { HistoryMode } from './modes/HistoryMode';
import { EmergencyMode } from './modes/EmergencyMode';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const { currentMode } = useStore();

  const renderMode = () => {
    switch (currentMode) {
      case 'overview':
        return <OverviewMode />;
      case 'routine':
        return <RoutineMode />;
      case 'ecg':
        return <ECGMode />;
      case 'history':
        return <HistoryMode />;
      case 'emergency':
        return <EmergencyMode />;
      default:
        return <OverviewMode />;
    }
  };

  return (
    <AppShell>
      <AnimatePresence mode="wait">
        <motion.div
          key={currentMode}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          className="w-full"
        >
          {renderMode()}
        </motion.div>
      </AnimatePresence>
    </AppShell>
  );
}

export default App;
