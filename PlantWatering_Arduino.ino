//Vars
int i  = 0;
int sensorUno = A0;
int sensorDue = A1;

int sensorUnoValue = 0;
int sensorDueValue = 0;

// Constants (Original mesurement: 365 dry, 265 wet)
int wetUno = 290;
int dryUno = 350;
int wetDue = 290;
int dryDue = 350;

const int size = 180; // 3min
int valUno = 0;
int valDue = 0;
int dataUno[size];
int dataDue[size];
int sumUno = 0;
int sumDue = 0;
int avgUno = 0;
int avgDue = 0;
int insertAt = 0;
bool notFull = true;
int count = -1;

void setup() {
  Serial.begin(9600); 
}

void loop() {
  count = (count + 1) % (size*10);

  sensorUnoValue = analogRead(sensorUno);
  sensorDueValue = analogRead(sensorDue);

  valUno= convertedMoistureUno(sensorUnoValue);
  valDue = convertedMoistureDue(sensorDueValue);

  if ((count % 10) == 0){ // Save one val every second 
    insertAt = count/10;
    dataUno[insertAt] = valUno;
    dataDue[insertAt] = valDue;
  } 

  sumUno = 0;
  sumDue = 0;
  
  for (int i = 0; i < size; i++) {     
      sumUno = sumUno + dataUno[i];    
      sumDue = sumDue + dataDue[i];    

  }      

  if (notFull){
  
    avgUno = sumUno / (insertAt+1);
    avgDue = sumDue / (insertAt+1);

    if ((insertAt+1) == size){
      notFull = false;
    }

  } else {  
    avgUno = sumUno / size;
    avgDue = sumDue / size;
  }

  //Send sensorvalues as array [val1, avg1, val2, avg2]
  Serial.println(String(valUno) + "," + String(avgUno) + "," + String(valDue) + "," + String(avgDue));

  delay(100); // results in average over last 42 seconds

}


int convertedMoistureUno(int rawValue){

  //Compensate to some extent
  if (rawValue < wetUno) {
    wetUno = rawValue;
  } 

  if (rawValue > dryUno) {
    dryUno = rawValue;
  }
  
  return map(rawValue, wetUno, dryUno, 100, 0);

}

int convertedMoistureDue(int rawValue){

  //Compensate to some extent
  if (rawValue < wetDue) {
    wetDue = rawValue;
  } 

  if (rawValue > dryDue) {
    dryDue = rawValue;
  }
  
  return map(rawValue, wetDue, dryDue, 100, 0);

}