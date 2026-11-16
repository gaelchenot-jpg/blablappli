plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "fr.blablappli"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.blablappli"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
        versionName = "0.1." + (System.getenv("GITHUB_RUN_NUMBER") ?: "0")
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a") }
    }

    signingConfigs {
        create("blablappli") {
            // Clé de signature personnelle (appli à usage privé) : la même clé à
            // chaque version permet d'installer les mises à jour par-dessus.
            storeFile = file("blablappli.keystore")
            storePassword = "blablappli"
            keyAlias = "blablappli"
            keyPassword = "blablappli"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("blablappli")
        }
        debug {
            signingConfig = signingConfigs.getByName("blablappli")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    androidResources {
        // le modèle vocal ne doit pas être compressé
        noCompress += listOf("mdl", "fst", "int", "conf", "dat", "txt", "ie", "mat", "raw")
    }
}

dependencies {
    implementation("com.alphacephei:vosk-android:0.3.75")
    implementation("net.java.dev.jna:jna:5.18.1@aar")
    testImplementation("junit:junit:4.13.2")
}
