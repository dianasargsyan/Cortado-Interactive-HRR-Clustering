import { environment } from 'src/environments/environment';
import { ElectronService } from './services/electronService/electron.service';
import { ElectronDummyService } from './services/electronService/electron-dummy.service';
import { ElectronInterface } from './services/electronService/electron-interface';

export function electronServiceFactory(): ElectronInterface {
  // Provide the ElectronService if the environment is Electron
  if (environment.electron) {
    return new ElectronService();
  } else {
    console.error(
      'Cannot provide normal ElectronService when running in browser. Instead providing dummy with limited functionallity'
    );
    return new ElectronDummyService();
  }
}
